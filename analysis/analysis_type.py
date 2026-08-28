from enum import Enum, auto

class AnalysisItemType(Enum):
    Base = 0
    Patent = auto()
    Paper = auto()
    PaperNTURanking = auto()
    PaperPresidentReport = auto()
    ESI = auto()
    PaperPresidentReportESI = auto()
    Patent_Clean = auto()