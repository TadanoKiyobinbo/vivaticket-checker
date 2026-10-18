import os
import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ==========================================
# 1. 【基本設定】監視するURLや保存ファイルの準備
# ==========================================
# 監視したい2つのチケットページのURL
URL_ADMISSION = "https://cenacolovinciano.vivaticket.it/en/event/cenacolo-vinciano/151991?idt=2547"
URL_GUIDED = "https://cenacolovinciano.vivaticket.it/en/event/cenacolo-visite-guidate-a-orario-fisso-in-inglese/238363?idt=2547"

# Discordに通知を送るための秘密のURL（GitHubのSecretsから読み込みます）
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# 前回の空き状況を記憶しておくためのファイル名
STATUS_FILE = "status.json"


# ==========================================
# 2. 【状態の保存・読み込み】前回どうだったかを管理
# ==========================================
def load_previous_status():
    """前回のチェック時に「空きがあったかどうか」をファイルから読み込む関数"""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    # ファイルがまだない初回は「両方とも空きなし（False）」からスタート
    return {"admission": False, "guided": False}

def save_current_status(status_data):
    """現在の空き状況をファイルに書き込んで保存する関数"""
    with open(STATUS_FILE, "w") as f:
        json.dump(status_data, f)


# ==========================================
# 3. 【メインのチェック処理】サイトを開いて空きを探す
# ==========================================
def check_has_availability(page, url):
    """
    ブラウザを使ってページを開き、
    - 10月なら自動で11月のカレンダーに切り替え
    - 選択できる日付（緑色の枠）があるかチェック
    をする関数です。
    """
    try:
        # 指定したURLのページにアクセスし、読み込みが完了するのを待つ
        page.goto(url, timeout=30000)
        page.wait_for_load_state("networkidle")
        
        # --------------------------------------------------
        # 💡 【重要】10月中は自動で「翌月（11月）」にカレンダーを進める処理
        # --------------------------------------------------
        current_month = datetime.now().month  # 今月の月（例: 10）
        target_month = 11                     # あなたが見たい月（11）
        
        if current_month < target_month:
            try:
                # カレンダーの「次へ（翌月）」ボタンを自動で探してクリックする
                next_button = page.locator("a.ui-datepicker-next, button.next, .calendar-next, [aria-label*='Next' i], [aria-label*='Successivo' i]").first
                if next_button.is_visible():
                    next_button.click()
                    page.wait_for_timeout(2000) # 画面が切り替わるのを2秒待つ
                    print("10月の表示から、11月（翌月）のカレンダーへ自動移動しました。")
            except Exception as e:
                print(f"翌月ボタンのクリックに失敗しましたが、処理を続行します: {e}")

        # --------------------------------------------------
        # カレンダーの中に「選択できる日付（緑色のリンク）」があるか解析
        # --------------------------------------------------
        content = page.content()
        soup = BeautifulSoup(content, "html.parser")
        
        # ページ内のすべてのリンク（<a>タグ）をチェック
        links = soup.select("a")
        active_dates = 0
        
        for link in links:
            text = link.get_text().strip()
            # 1〜31の数字（日付）であるもの
            if text.isdigit() and 1 <= int(text) <= 31:
                classes = str(link.get("class", [])).lower()
                parent_classes = str(link.parent.get("class", [])).lower()
                
                # 「disabled（無効＝グレーアウト）」という文字が入っていなければ、選択可能（緑色）とみなす
                if "disabled" not in classes and "disabled" not in parent_classes:
                    active_dates += 1
                    
        # 補助的にページ内に「available」という文字があるかも確認
        has_keyword = "available" in content.lower() or "disponibile" in content.lower()
        
        # アクティブな日付が1つ以上ある、またはキーワードがあれば「空きあり（True）」と判定
        return (active_dates > 0) or has_keyword

    except Exception as e:
        print(f"チェック中にエラーが発生しました ({url}): {e}")
        return None


# ==========================================
# 4. 【全体の統括】比較して、変化があった時だけ通知する
# ==========================================
def main():
    # 前回の状態（空きがあったかどうか）を思い出す
    prev_status = load_previous_status()
    was_admission_avail = prev_status.get("admission", False)
    was_guided_avail = prev_status.get("guided", False)
    
    # 裏側でブラウザ（Chromium）を起動してチェックを実行
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("通常入場券をチェック中（ブラウザ操作）...")
        curr_admission_avail = check_has_availability(page, URL_ADMISSION)
        
        print("英語ガイドツアーをチェック中（ブラウザ操作）...")
        curr_guided_avail = check_has_availability(page, URL_GUIDED)
        
        browser.close()
        
    # エラーなどで判定できなかった場合は、前回の状態をそのまま引き継ぐ
    if curr_admission_avail is None:
        curr_admission_avail = was_admission_avail
    if curr_guided_avail is None:
        curr_guided_avail = was_guided_avail

    # --------------------------------------------------
    # 【通常入場券】の変化をチェック ＆ 通知判定
    # --------------------------------------------------
    # 条件：「前回は空きなし(False)」かつ「今回空きあり(True)」に変わった瞬間だけ！
    if curr_admission_avail and not was_admission_avail:
        message = {
            "content": f"🚨 **【速報：通常入場券に空き枠を検知！】**\n最後の晩餐の通常入場券の11月カレンダーに選択可能な（緑色の）日付が現れました！\n今すぐ急いで取得してください！\n🔗 {URL_ADMISSION}"
        }
        if DISCORD_WEBHOOK_URL:
            requests.post(DISCORD_WEBHOOK_URL, json=message)
        print("【通知送信】通常入場券の空きを検知しました！")
    elif curr_admission_avail and was_admission_avail:
        print("通常入場券は空きが続いていますが、すでに通知済みのため重複通知をスキップします。")
    else:
        print("通常入場券は現在空きがありません。")

    # --------------------------------------------------
    # 【英語ガイドツアー】の変化をチェック ＆ 通知判定
    # --------------------------------------------------
    # 条件：「前回は空きなし(False)」かつ「今回空きあり(True)」に変わった瞬間だけ！
    if curr_guided_avail and not was_guided_avail:
        message = {
            "content": f"🚨 **【速報：英語ガイドツアーに空き枠を検知！】**\n最後の晩餐の英語ガイドツアーの11月カレンダーに選択可能な（緑色の）日付が現れました！\n今すぐ急いで取得してください！\n🔗 {URL_GUIDED}"
        }
        if DISCORD_WEBHOOK_URL:
            requests.post(DISCORD_WEBHOOK_URL, json=message)
        print("【通知送信】英語ガイドツアーの空きを検知しました！")
    elif curr_guided_avail and was_guided_avail:
        print("英語ガイドツアーは空きが続いていますが、すでに通知済みのため重複通知をスキップします。")
    else:
        print("英語ガイドツアーは現在空きがありません。")

    # --------------------------------------------------
    # 次回と比較するために、今回の最新状態をファイルに保存
    # --------------------------------------------------
    save_current_status({
        "admission": curr_admission_avail,
        "guided": curr_guided_avail
    })

if __name__ == "__main__":
    main()
