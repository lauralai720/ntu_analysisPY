# PRIS 錯誤Exception定義

class PRISError(Exception):
    def __init__(self, message: str): #error code 先移除, code: int = 500):
        # 呼叫父類別 Exception，這樣才能正常顯示錯誤訊息
        super().__init__(message)
        # 額外擴充自訂屬性
        # self.code = code

    def __str__(self):
        # return f"[Error {self.code}] {self.args[0]}"
        return f"[Error] {self.args[0]}"