from dataclasses import field, dataclass
import re
from enum import Enum

from exceptions import PRISError
import common.db_schema as db_schema

class PaperOrg2ndCodeType(Enum):
    MAIN = 1    # 主編碼
    SECOND = 2  # 二級編碼
    THIRD = 3   # 三級編碼
    FULL = 4    # 完整編碼

class AuthorIndex(Enum):
    NotLimited = 0
    FirstAuthor = 1
    Reprint = 2
    FirstOrReprint = 3
    

FORMATS_2ND: list[tuple[str, PaperOrg2ndCodeType]] = [
    (r"OtherCenter", PaperOrg2ndCodeType.SECOND),
    (r"^[A-Z]{3}[0-9]{6}\*$", PaperOrg2ndCodeType.MAIN),
    (r"^[A-Z]{3}[0-9]{8}\*$", PaperOrg2ndCodeType.SECOND),
    (r"^[A-Z]{3}[0-9]{10}\*$", PaperOrg2ndCodeType.THIRD),
    (r"^[A-Z]{3}[0-9]{6}%$", PaperOrg2ndCodeType.MAIN),
    (r"^[A-Z]{3}[0-9]{8}%$", PaperOrg2ndCodeType.SECOND),
    (r"^[A-Z]{3}[0-9]{9}%$", PaperOrg2ndCodeType.SECOND),  # for TWU000001127%
    (r"^[A-Z]{3}[0-9]{10}%$", PaperOrg2ndCodeType.THIRD),
    (r"^[A-Z]{3}[0-9]{12}$", PaperOrg2ndCodeType.FULL),
]

class PaperSQLCmd:
    @staticmethod
    def get_value_where_like_org_2nd_cmd( org_serial_like:str) -> str:
        return (f"SELECT DISTINCT {db_schema.schema.OrgSerialColumnName}, "+
            f"{db_schema.schema.OrgName1CHColumnName}, "+
            f"{db_schema.schema.OrgName2CHColumnName}, "+
            f"{db_schema.schema.OrgName3CHColumnName}, "+
            f"{db_schema.schema.OrgName4CHColumnName}, "+
            f"{db_schema.schema.OrgName1ENColumnName}, "+
            f"{db_schema.schema.OrgName2ENColumnName}, "+
            f"{db_schema.schema.OrgName3ENColumnName}, "+
            f"{db_schema.schema.OrgName4ENColumnName} "+
            f"FROM {db_schema.schema.OrgAcSecondTableName} "+
            f"WHERE  substring({db_schema.schema.OrgSerialColumnName},1,11) COLLATE SQL_Latin1_General_CP1_CI_AS IN (SELECT DISTINCT  substring({db_schema.schema.OrgColumnName},1,11) FROM {db_schema.schema.Org2ndTableName}) "+
            f"AND {db_schema.schema.OrgSerialColumnName} != '' AND {db_schema.schema.OrgSerialColumnName} NOT LIKE 'XXX%'"+
            f"AND {db_schema.schema.OrgSerialColumnName} LIKE N'{org_serial_like}%' AND OrgName1En !='' "+
            f"ORDER BY {db_schema.schema.OrgSerialColumnName} ASC")
    @staticmethod
    def get_value_where_like_org_25nd_cmd( org_serial_like:str) -> str:
        ## 台大附設醫院（TWU000001127999）需要將台大癌醫（TWU0000011254）及行政單位（TWU000001129100）加進去
        ## 台大癌醫（TWU0000011254）的順位排在附設醫院雲林分院之後
        return (f"SELECT DISTINCT {db_schema.schema.OrgSerialColumnName}, "+
            f"{db_schema.schema.OrgName1CHColumnName}, "+
            f"{db_schema.schema.OrgName2CHColumnName}, "+
            f"{db_schema.schema.OrgName3CHColumnName}, "+
            f"{db_schema.schema.OrgName4CHColumnName}, "+
            f"{db_schema.schema.OrgName1ENColumnName}, "+
            f"{db_schema.schema.OrgName2ENColumnName}, "+
            f"{db_schema.schema.OrgName3ENColumnName}, "+
            f"{db_schema.schema.OrgName4ENColumnName}, "+
            f"case substring(OrgSerial,12,2) when '54' then '771'+substring(OrgSerial,15,1) else substring(OrgSerial,12,4) end as orgIndex "+
            f"FROM {db_schema.schema.OrgAcSecondTableName} "+
            f"WHERE  substring({db_schema.schema.OrgSerialColumnName},1,12) COLLATE SQL_Latin1_General_CP1_CI_AS IN (SELECT DISTINCT  substring({db_schema.schema.OrgColumnName},1,12) FROM {db_schema.schema.Org2ndTableName}) "+
            f"AND {db_schema.schema.OrgSerialColumnName} != '' AND {db_schema.schema.OrgSerialColumnName} NOT LIKE 'XXX%'"+
            f"AND ({db_schema.schema.OrgSerialColumnName} LIKE N'{org_serial_like}%' or OrgSerial like N'TWU0000011254%' or OrgSerial like N'TWU0000011291%')"+
            f"AND OrgSerial != 'TWU000001127999' AND OrgName1En !='' "+
            f"ORDER BY orgIndex ASC ")
        


class PaperOrgItem:
    REG = re.compile(r"^[A-Z]{1,3}[0-9]{5,6}$")
    def __init__(self, serial:str = ""):
        self.serial : str = serial
        if not self.valid:
            raise PRISError(f"機構編碼格式輸入錯誤: {self.serial}")

    @property
    def valid(self)->bool:
        return self.format_correct(self.serial)

    @staticmethod
    def format_correct(serial:str)->bool:
        return bool(PaperOrgItem.REG.match(serial))

class PaperOrg2ndItem(PaperOrgItem):
    def __init__(self, serial = ""):
        self.serial = serial

        matched = False
        for pattern, code_type in FORMATS_2ND:
            if bool(re.match(pattern, self.serial)):
                self.code_type = code_type
                matched = True
                break

        if not matched:
            raise PRISError(f"機構編碼格式輸入錯誤: {self.serial}")

        self.query_var = self.serial.replace('*', '%')

## PaperOrgSelectedValueItem
class PaperOrgSelectItem:
    def __init__(self, raw_serial:str, org_name_1:str|None = None, org_name_2:str|None= None):
        self.raw_serial : str = raw_serial
        self.org_name_ch : str = org_name_1 if org_name_1 else ""
        self.org_name_en : str = org_name_2 if org_name_2 else ""
        self.items : list[PaperOrgItem] = []

        split_serials = [x.strip() for x in raw_serial.split(",")]
        for s in split_serials:
            if PaperOrgItem.format_correct(s):
                self.items.append(PaperOrgItem(s))
            else:
                self.items.append(PaperOrg2ndItem(s))
        ## 事後再補判斷serial是否正確
    @property
    def org_name(self)->str:
        name = self.org_name_en + ("" if self.org_name_en == "" or self.org_name_ch == "" else "-"+ self.org_name_ch)
        return name

class PaperOrgSelectedValue:
    def __init__(self):
        self.items : list[PaperOrgSelectItem] = []
        self.author_index :AuthorIndex = AuthorIndex.NotLimited
        self.merge_items : dict = {}

    def add(self, org_item:PaperOrgSelectItem):
        self.items.append(org_item)

    def find_org(self, org_serial:str)->tuple[str,str,str]:
        res = next((org for org in self.items if org_serial == org.raw_serial), None)
        return res.raw_serial, res.org_name_ch, res.org_name_en

@dataclass
class PaperOrg:
    org_serial:str
    name_ch:str = ""
    name_en:str = ""

class PaperOrg2nd(PaperOrg):
    def __init__(self, serial, name_ch_1, name_ch_2,name_ch_3,name_ch_4,name_en_1,name_en_2,name_en_3,name_en_4):
        super().__init__(org_serial=serial)
        self.code_type = self.get_code_type()
        self.name_ch = self.get_name(name_ch_1, name_ch_2,name_ch_3,name_ch_4)
        self.name_en = self.get_name(name_en_1,name_en_2,name_en_3,name_en_4)
        
        # self.name_ch_1 = name_ch_1
        # self.name_ch_2 = name_ch_2
        # self.name_ch_3 = name_ch_3
        # self.name_ch_4 = name_ch_4
        # self.name_en_1 = name_en_1
        # self.name_en_2 = name_en_2
        # self.name_en_3 = name_en_3
        # self.name_en_4 = name_en_4
        
    def get_code_type(self) -> PaperOrg2ndCodeType:
        if self.org_serial[9:11] == "00":
            return PaperOrg2ndCodeType.MAIN
        if self.org_serial[11:13] == "00":
            return PaperOrg2ndCodeType.SECOND
        if self.org_serial[13:15] == "00":
            return PaperOrg2ndCodeType.THIRD
        return PaperOrg2ndCodeType.FULL

    def get_name(self,name1:str, name2:str,name3:str,name4:str) -> str:
        if self.code_type == PaperOrg2ndCodeType.MAIN:
            return name1
        if self.code_type == PaperOrg2ndCodeType.SECOND:
            return f"{name1}, {name2}"
        if self.code_type == PaperOrg2ndCodeType.THIRD:
            return f"{name1}, {name2}, {name3}"
        return (f"{name1}, {name2}, {name3}, {name4}").replace("''s", "'s")




