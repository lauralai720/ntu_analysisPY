# 這裡定義全域變數，模擬 Singleton 的狀態
lang = "zh-TW"

def set_lang(new_lang):
    global lang
    lang = new_lang