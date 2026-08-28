
## 這是跟匯出UI相關，用CLI暫時略過
from dataclasses import dataclass

@dataclass
class ExportDetail:
    filter: str
    title: str
    filename : str
    used_folder: bool
    # export :  // 輸出介面用的樣子，先不用他
