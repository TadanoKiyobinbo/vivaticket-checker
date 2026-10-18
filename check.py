import os
import random
import time
import requests
from bs4 import BeautifulSoup

# 監視する2つのチケットの個別URL
URL_ADMISSION = "https://cenacolovinciano.vivaticket.it/en/event/cenacolo-vinciano/151991?idt=2547"
URL_GUIDED = "https://cenacolovinciano.vivaticket.it/en/event/cenacolo-visite-guidate-a-orario-fisso-in-inglese/238363?idt=2547"

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
}

def check_ticket(url, ticket_name):
    """特定のチケットURLをチェックして、空きがあれば通知する関数"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text()

        # 「BUY」または「ACQUISTA」の表示があるか検知
        if "BUY" in page_text or "ACQUISTA" in page_text:
            message = {
                "content": f"🚨 **【空き検知！】**\n**{ticket_name}** に空きが出た可能性があります！\n🔗 {url}"
            }
            if DISCORD_WEBHOOK_URL:
                requests.post(DISCORD_WEBHOOK_URL, json=message)
            print(f"{ticket_name} の空きを検知して通知しました。")
        else:
            print(f"{ticket_name}: 現在空きはありません。")

    except Exception as e:
        print(f"{ticket_name} のチェック中にエラーが発生しました: {e}")

def main():
    # 1. Admission ticket (通常入場券) をチェック
    check_ticket(URL_ADMISSION, "Admission ticket (通常入場券)")
    
    # サイトに負荷をかけないよう、数秒ランダム待機
    time.sleep(random.randint(3, 7))
    
    # 2. English guided tour (英語ガイド) をチェック
    check_ticket(URL_GUIDED, "Set times guided tours in English (英語ガイド)")

if __name__ == "__main__":
    main()
