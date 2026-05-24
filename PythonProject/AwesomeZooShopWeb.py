import streamlit as st
import requests
from supabase import create_client, Client
from streamlit import config as _config
from config import SUPABASE_URL, SUPABASE_KEY, BOT_TOKEN, NOVA_POSHTA_API_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

_config.set_option("theme.base", "light")
_config.set_option("server.headless", True)

BOT_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ==============================================================================
# 🎯 ІНТЕГРАЦІЯ GOOGLE TAG MANAGER (КОД КОНТЕЙНЕРА: GTM-K7VCWMCB)
# ==============================================================================
# Впровадження основної частини скрипта та резервного тегу <noscript>
st.markdown("""
<script>
  (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
  new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
  j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
  'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
  })(window,document,'script','dataLayer','GTM-K7VCWMCB');
</script>
<noscript>
  <iframe src="https://www.googletagmanager.com/ns.html?id=GTM-K7VCWMCB"
          height="0" width="0" style="display:none;visibility:hidden"></iframe>
</noscript>
<script>
  (function() {
    // Логіка для Telegram WebApp (передача initData в URL)
    if (window.Telegram && window.Telegram.WebApp) {
      const init = Telegram.WebApp.initData;
      if (init && !window.location.search.includes("initData=")) {
        const qs = window.location.search ? window.location.search + "&" : "?";
        window.location.href = window.location.pathname + qs + "initData=" + encodeURIComponent(init);
      }
    }
  })();
</script>
""", unsafe_allow_html=True)

# Безпечна перевірка пошукових роботів Google
def is_google_bot():
    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            user_agent = st.context.headers.get("User-Agent", "")
            if "Googlebot" in user_agent or "Google-PageSpeed" in user_agent:
                return True
    except:
        pass
    return False
