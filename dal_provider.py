"""
提供全域共用的 DataAccessLayer instance。

任何檔案要用 DataAccessLayer,一律透過這裡的 get_dal() 取得,
不要自己 DataAccessLayer(),確保整個程式只有一份 instance,
不會重複初始化 .NET runtime、重複載入 DLL。
"""

from data_access_layer import DataAccessLayer

_dal: DataAccessLayer | None = None

def get_dal() -> DataAccessLayer:
    global _dal
    if _dal is None:
        _dal = DataAccessLayer()
    return _dal
