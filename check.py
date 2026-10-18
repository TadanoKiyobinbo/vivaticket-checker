import os
import json
import requests
from bs4 import BeautifulSoup

# ==========================================
# 1. 基本設定（監視するURLなど）
# ==========================================
URL_ADMISSION = "https://cenacolovinciano.vivaticket.it/en/event/cenacolo-vinciano/151991?idt=2547"
URL_GUIDED = "https://cenacolovinciano.vivaticket.it/en/event/cenacolo-visite-guidate-a-orario-fisso-in-inglese/238363?idt=2547"

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
STATUS_FILE = "status.json"

# 人間のブラウザからのアクセスに見せかけるための設定
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
}


# ==========================================
# 2. 前回の状態を保存・読み込みする仕組み
# ==========================================
def load_previous_status():
    """前回チェックしたときの空き状況（True/False）をファイルから読み込む"""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    # 初回（ファイルがないとき）は「両方とも空きなし（False）」からスタート
    return {"admission": False, "guided": False}

def save_current_status(status_data):
    """現在の空き状況をファイルに保存する"""
    with open(STATUS_FILE, "w") as f:
        json.dump(status_data, f)


# ==========================================
# 3. カレンダーの「緑色（空き）」を判定する関数
# ==========================================
def check_has_availability(url):
    """指定したURLのページを読み込み、カレンダーに選択可能な日（緑色）があるか調べる"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # ページ内にあるすべてのリンク（<a>タグ）をチェック
        calendar_links = soup.select("a")
        valid_date_links = 0
        
        for link in calendar_links:
            text = link.get_text().strip()
            # 1〜31の数字（日付）かつ、カレンダーエリアにあるものをカウント
            if text.isdigit() and 1 <= int(text) <= 31:
                parent_classes = str(link.parent.get("class", [])).lower()
                if "calendar" in parent_classes or "day" in parent_classes or "month" in parent_classes or "av" in parent_classes:
                    valid_date_links += 1
                    
        # 選択できる日付のリンクが1つ以上あれば「空きあり（True）」
        return valid_date_links > 0
        
    except Exception as e:
        print(f"チェック中にエラーが発生しました ({url}): {e}")
        return None


# ==========================================
# 4. メインの処理（チェックして、変化した時だけ通知）
# ==========================================
def main():
    # 前回の状態を思い出す
    prev_status = load_previous_status()
    was_admission_avail = prev_status.get("admission", False)
    was_guided_avail = prev_status.get("guided", False)
    
    # 1. 通常入場券の空き状況をチェック
    print("通常入場券をチェック中...")
    curr_admission_avail = check_has_availability(URL_ADMISSION)
    
    # 2. 英語ガイドツアーの空き状況をチェック
    print("英語ガイドツアーをチェック中...")
    curr_guided_avail = check_has_availability(URL_GUIDED)
    
    # エラーなどで判定できなかった場合は前回の状態を維持
    if curr_admission_avail is None:
        curr_admission_avail = was_admission_avail
    if curr_guided_avail is None:
        curr_guided_avail = was_guided_avail

    # ------------------------------------------
    # 【通常入場券】の変化をチェック ＆ 通知
    # ------------------------------------------
    # 「前回は空きなし(False) ➔ 今回空きあり(True)」に変わった瞬間だけ通知
    if curr_admission_avail and not was_admission_avail:
        message = {
            "content": f"🚨 **【速報：通常入場券に空き枠を検知！】**\n最後の晩餐の通常入場券のカレンダーに選択可能な（緑色の）日付が現れました！\n今すぐ急いで取得してください！\n🔗 {URL_ADMISSION}"
        }
        if DISCORD_WEBHOOK_URL:
            requests.post(DISCORD_WEBHOOK_URL, json=message)
        print("【通知送信】通常入場券の空きを検知しました！")
    elif curr_admission_avail and was_admission_avail:
        print("通常入場券は空きが続いていますが、すでに通知済みのため重複通知をスキップします。")
    else:
        print("通常入場券は現在空きがありません（すべてグレーアウト）。")

    # ------------------------------------------
    # 【英語ガイドツアー】の変化をチェック ＆ 通知
    # ------------------------------------------
    # 「前回は空きなし(False) ➔ 今回空きあり(True)」に変わった瞬間だけ通知
    if curr_guided_avail and not was_guided_avail:
        message = {
            "content": f"🚨 **【速報：英語ガイドツアーに空き枠を検知！】**\n最後の晩餐の英語ガイドツアーのカレンダーに選択可能な（緑色の）日付が現れました！\n今すぐ急いで取得してください！\n🔗 {URL_GUIDED}"
        }
        if DISCORD_WEBHOOK_URL:
            requests.post(DISCORD_WEBHOOK_URL, json=message)
        print("【通知送信】英語ガイドツアーの空きを検知しました！")
    elif curr_guided_avail and was_guided_avail:
        print("英語ガイドツアーは空きが続いていますが、すでに通知済みのため重複通知をスキップします。")
    else:
        print("英語ガイドツアーは現在空きがありません（すべてグレーアウト）。")

    # 最新の状態をファイルに保存して次回に備える
    save_current_status({
        "admission": curr_admission_avail,
        "guided": curr_guided_avail
    })

if __name__ == "__main__":
    main()
