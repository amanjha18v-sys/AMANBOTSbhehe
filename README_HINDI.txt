ZYTRON-STYLE REFERRAL KEY BOT
=============================

FEATURES
- Screenshot-style Telegram menu: Refer, Get Key, Verify Channel, Profile
- Unique referral link for each user
- 1 coin per new referred user after channel membership verification
- 5 coins = 1 key
- Duplicate referral protection and one-time claim per user
- Admin commands: /addkey KEY1 KEY2 ... and /stats
- SQLite database

ANDROID / TELEBOTHOST SETUP
1. ZIP extract karein.
2. TeleBotHost me Python bot/project upload karein (main.py, requirements.txt, Procfile).
3. Environment variables set karein:
   BOT_TOKEN = BotFather se naya token
   ADMIN_ID = 5191323229
   CHANNEL_ID = @YourChannelUsername (ya private channel ka -100... ID)
   CHANNEL_LINK = channel invite link
   BOT_USERNAME = bot username without @
   REFS_REQUIRED = 5
4. Bot ko required channel ka ADMIN banayein, taaki get_chat_member se membership verify ho.
5. Start command: python main.py
6. Bot me admin account se /addkey KEY001 KEY002 KEY003 bhejein.
7. /stats se users, referrals aur stock check karein.

IMPORTANT
- Channel ID/link apne actual channel ke hisab se replace karna zaroori hai.
- Bot token ko public ZIP/chat me mat rakhein. Agar token pehle share hua hai to BotFather se revoke karke naya token use karein.
- Keys tabhi auto-deliver hongi jab admin /addkey se stock add karega.
- API key generation ka exact integration provider ke API URL, request parameters, authentication aur response example ke bina safely configure nahi ho sakta. KEY_API_URL placeholder live API integration nahi hai.
- SQLite file ko persistent storage par rakhein; host restart par ephemeral storage ho to database lose ho sakta hai.
- Referral credit tabhi hota hai jab referred user pehli baar bot start kare aur channel verification pass kare. Existing users, self-referrals aur repeat checks count nahi hote.
