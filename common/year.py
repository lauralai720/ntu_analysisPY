import re

from exceptions import PRISError

class YearType :
    WholeYear = 0
    FirstHalf = 1
    SecondHalf = 2

class SupportYearType :
    WholeYear = 0b0001
    HalfYear = 0b0010

class Year :
    SupportedYearType = SupportYearType.WholeYear

    def __init__(self, *args):
        self.is_single = None
        self._year = 0
        self.from_year = 0
        self.to_year = 0
        self.type = YearType.WholeYear
        self.from_type = YearType.WholeYear
        self.to_type = YearType.WholeYear

        if len(args) == 1 and isinstance(args[0], int):
            # Year(int year)
            self.is_single = True
            self._year = args[0]
        elif len(args) == 2 and all(isinstance(x, int) for x in args):
            # Year(int fromYear, int toYear)
            from_year, to_year = args
            if from_year >= to_year:
                raise PRISError(f"起始年({from_year})不能大於等於結束年({to_year})")
            self.is_single = False
            self.from_year = from_year
            self.to_year = to_year
        elif len(args) == 1 and isinstance(args[0], str):
            # Year(string strYear)
            str_year = args[0]
            rgx_single_year = re.compile(r"^\d{4}$")
            rgx_range_year = re.compile(r"^\d{4}-\d{4}$")
            rgx_single_year_in_half = re.compile(r"^\d{4}H[1-2]$")
            rgx_range_year_in_half = re.compile(r"^\d{4}H[1-2]-\d{4}H[1-2]$")
            if rgx_single_year.match(str_year) and (Year.SupportedYearType & SupportYearType.WholeYear):
                self.is_single = True
                self._year = int(str_year)
            elif rgx_range_year.match(str_year) and (Year.SupportedYearType & SupportYearType.WholeYear):
                self.is_single = False
                splited = str_year.split('-')
                self.from_year = int (splited[0])
                self.to_year = int(splited[1])
                if self.from_year >= self.to_year:
                    raise PRISError(f"起始年({self.from_year})不能大於等於結束年({self.to_year})")
            elif rgx_single_year_in_half.match(str_year) and(Year.SupportedYearType & SupportYearType.HalfYear) :
                self.is_single = True
                splited = str_year.split('H')
                self._year = int (splited[0])
                self.type = YearType.FirstHalf if splited[1] == "1" else YearType.SecondHalf
            elif rgx_range_year_in_half.match(str_year) and (Year.SupportedYearType & SupportYearType.HalfYear):
                self.is_single = False
                splited = str_year.split('-')
                from_splited = splited[0].split('H')
                self.from_year = int (from_splited[0])
                self.from_type = YearType.FirstHalf if from_splited[1] == "1" else YearType.SecondHalf
                to_splited = splited[1].split('H')
                self.to_year = int(to_splited[0])
                self.to_type = YearType.FirstHalf if to_splited[1] == "1" else YearType.SecondHalf
            else:
                raise PRISError(f"年代格式錯誤: {str_year}")
        else:
            raise PRISError("Year 初始化參數錯誤")

    @property
    def is_whole_year(self) :
        return (self.type == YearType.WholeYear and
                self.from_type == YearType.WholeYear and
                self.to_type == YearType.WholeYear)

    @property
    def year(self) :
        if self.is_single:
            return self._year
        return (self.from_year, self.to_year)

    @property
    def year_type(self):
        if self.is_single:
            return self.type
        return (self.from_type, self.to_type)

    def add(self, num):
        if self.is_single:
            return Year(self._year + num)
        else:
            return Year(self.from_year + num, self.to_year + num)

    def to_int(self) -> int:
        if not self.is_whole_year:
            raise PRISError("年代須為完整年度才能轉換 Int 型態")
        if self.is_single:
            return self._year
        else:
            raise PRISError("年代為區間值, 無法轉換成 Int 型態")

    def __str__(self): # toString
        if self.is_single:
            if self.type == YearType.WholeYear:
                return str(self._year)
            elif self.type == YearType.FirstHalf:
                return f"{self._year}H1"
            else:
                return f"{self._year}H2"
        from_type_str = "H1" if self.from_type == YearType.FirstHalf else ("H2" if self.from_type == YearType.SecondHalf else "")
        to_type_str = "H1" if self.to_type == YearType.FirstHalf else ("H2" if self.to_type == YearType.SecondHalf else "")
        return f"{self.from_year}{from_type_str}-{self.to_year}{to_type_str}"

    def __eq__(self, other): #Equals
        if not isinstance(other, Year):
            return False
        if other.is_single:
            if self.is_single:
                return self.year == other.year and self.type == other.type
            return False
        if not self.is_single:
            return (self.year == other.year and
                    self.from_type == other.from_type and
                    self.to_type == other.to_type)
        return False

    def __hash__(self) : # GetHashCode
        map_ = {
            YearType.WholeYear: 23,
            YearType.FirstHalf: 31,
            YearType.SecondHalf: 37
        }
        if self.is_single:
            return self._year * map_[self.type]
        else:
            return self.from_year * self.to_year * map_[self.from_type] * map_[self.to_type]
