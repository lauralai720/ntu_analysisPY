"""
負責初始化 .NET runtime。
只有 DataAccessLayer 會呼叫這裡的東西,其他檔案不需要碰。
"""

_initialized = False


def init_dotnet(runtime: str = "netfx") -> None:
    global _initialized
    if _initialized:
        return

    from pythonnet import load

    try:
        load(runtime)
    except Exception as e:
        raise RuntimeError(
            f"載入 .NET runtime 失敗(runtime={runtime})。\n"
            f"常見原因:\n"
            f"  1. 機器上沒有安裝對應版本的 .NET\n"
            f"  2. pythonnet 版本跟 runtime 不相容,可考慮改用 pythonnet==2.5.2\n"
            f"原始錯誤:{e}"
        ) from e

    _initialized = True
