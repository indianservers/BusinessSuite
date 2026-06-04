from datetime import date, datetime, time
from datetime import date as date_type
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field


class ShiftBase(BaseModel):
    name: str
    code: Optional[str] = None
    start_time: time
    end_time: time
    grace_minutes: int = 10
    working_hours: Decimal = Decimal("8.0")
    is_night_shift: bool = False


class ShiftCreate(ShiftBase):
    pass


class ShiftSchema(ShiftBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class ShiftWeeklyOffCreate(BaseModel):
    shift_id: int
    weekday: int
    week_pattern: str = "all"


class ShiftWeeklyOffSchema(ShiftWeeklyOffCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class ShiftRosterAssignmentCreate(BaseModel):
    employee_id: int
    shift_id: int
    work_date: date
    status: str = "Published"


class ShiftRosterAssignmentSchema(ShiftRosterAssignmentCreate):
    id: int

    class Config:
        from_attributes = True


class HolidayBase(BaseModel):
    name: str
    holiday_date: date
    holiday_type: str = "National"
    description: Optional[str] = None
    applicable_branches: Optional[str] = None


class HolidayCreate(HolidayBase):
    pass


class HolidayCalendarBase(BaseModel):
    name: str
    holiday_date: date_type
    holiday_type: str = Field(default="National", pattern="^(National|Regional|Optional)$")
    description: Optional[str] = None
    applicable_branches: Optional[List[int]] = None


class HolidayCalendarCreate(HolidayCalendarBase):
    pass


class HolidayCalendarUpdate(BaseModel):
    name: Optional[str] = None
    holiday_date: Optional[date_type] = None
    holiday_type: Optional[str] = Field(default=None, pattern="^(National|Regional|Optional)$")
    description: Optional[str] = None
    applicable_branches: Optional[List[int]] = None


class HolidaySchema(HolidayBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class HolidayCalendarSchema(BaseModel):
    id: int
    name: str
    holiday_date: date_type
    holiday_type: str
    description: Optional[str] = None
    applicable_branches: List[int] = []
    is_active: bool
    created_at: Optional[datetime] = None


class CheckInRequest(BaseModel):
    check_in_location: Optional[str] = None
    check_in_ip: Optional[str] = None
    source: str = "Web"


class CheckOutRequest(BaseModel):
    check_out_location: Optional[str] = None
    check_out_ip: Optional[str] = None


class AttendancePunchCreate(BaseModel):
    employee_id: Optional[int] = None
    punch_time: datetime
    punch_type: str
    source: str = "Web"
    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    location_text: Optional[str] = None
    raw_payload: Optional[str] = None


class PunchRequest(BaseModel):
    punch_type: str = Field(pattern="^(IN|OUT|BREAK_IN|BREAK_OUT)$")
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    location_text: Optional[str] = None
    source: str = Field(default="web", pattern="^(web|mobile|Web|Mobile)$")


class AttendanceRegularizeRequest(BaseModel):
    date: date_type
    reason: str
    expected_check_in: Optional[datetime] = None
    expected_check_out: Optional[datetime] = None


class AttendancePunchSchema(AttendancePunchCreate):
    id: int
    employee_id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BiometricDeviceCreate(BaseModel):
    name: str
    vendor: str
    device_code: str
    location: Optional[str] = None
    sync_mode: str = "File Import"
    is_active: bool = True


class BiometricDeviceSchema(BiometricDeviceCreate):
    id: int
    last_sync_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BiometricImportRow(BaseModel):
    employee_id: int
    punch_time: datetime
    punch_type: str = "IN"
    device_user_id: Optional[str] = None


class BiometricImportRequest(BaseModel):
    device_id: Optional[int] = None
    source_filename: Optional[str] = None
    rows: List[BiometricImportRow]


class BiometricAdapterImportRequest(BaseModel):
    adapter: str = Field(default="generic", pattern="^(generic|essl|zkteco|mantra|csv)$")
    device_id: Optional[int] = None
    source_filename: Optional[str] = None
    csv_text: str
    employee_code_column: Optional[str] = None
    punch_time_column: Optional[str] = None
    punch_type_column: Optional[str] = None


class BiometricReconcileRequest(BaseModel):
    from_date: date
    to_date: date
    employee_id: Optional[int] = None
    recompute: bool = True


class BiometricImportBatchSchema(BaseModel):
    id: int
    device_id: Optional[int] = None
    source_filename: Optional[str] = None
    imported_rows: int
    skipped_rows: int
    error_rows: int
    status: str
    error_report_json: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GeoAttendancePolicyCreate(BaseModel):
    name: str
    latitude: Decimal
    longitude: Decimal
    radius_meters: int = 200
    require_selfie: bool = False
    require_qr: bool = False
    is_active: bool = True


class GeoAttendancePolicySchema(GeoAttendancePolicyCreate):
    id: int

    class Config:
        from_attributes = True


class GeoPunchRequest(BaseModel):
    punch_time: datetime
    punch_type: str = "IN"
    latitude: Decimal
    longitude: Decimal
    policy_id: Optional[int] = None
    selfie_url: Optional[str] = None
    qr_code: Optional[str] = None
    location_text: Optional[str] = None


class AttendancePunchProofSchema(BaseModel):
    id: int
    punch_id: int
    proof_type: str
    proof_url: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    qr_code: Optional[str] = None
    validation_status: str
    validation_message: Optional[str] = None

    class Config:
        from_attributes = True


class AttendanceMonthLockCreate(BaseModel):
    month: int
    year: int
    reason: Optional[str] = None


class AttendanceMonthLockSchema(AttendanceMonthLockCreate):
    id: int
    status: str
    locked_by: Optional[int] = None
    locked_at: Optional[datetime] = None
    unlocked_by: Optional[int] = None
    unlocked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AttendanceSchema(BaseModel):
    id: int
    employee_id: int
    attendance_date: date
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    shift_id: Optional[int] = None
    total_hours: Optional[Decimal] = None
    overtime_hours: Decimal = Decimal("0")
    late_minutes: int = 0
    early_exit_minutes: int = 0
    short_minutes: int = 0
    is_late: bool = False
    is_early_exit: bool = False
    is_short_hours: bool = False
    status: str
    source: str
    is_regularized: bool
    computed_at: Optional[datetime] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


class AttendanceRegisterRow(BaseModel):
    attendance_id: Optional[int] = None
    employee_id: int
    employee_code: Optional[str] = None
    employee_name: str
    department: Optional[str] = None
    branch: Optional[str] = None
    date: date
    status: str
    hours_worked: Decimal = Decimal("0")
    ot_hours: Decimal = Decimal("0")
    remarks: Optional[str] = None


class AttendanceRegisterResponse(BaseModel):
    items: List[AttendanceRegisterRow]
    total: int
    present: Decimal = Decimal("0")
    absent: Decimal = Decimal("0")
    half_day: Decimal = Decimal("0")
    holiday: Decimal = Decimal("0")
    weekly_off: Decimal = Decimal("0")
    wfh: Decimal = Decimal("0")
    overtime_hours: Decimal = Decimal("0")


class AttendanceManualEntry(BaseModel):
    employee_id: int
    date: date
    status: str = Field(pattern="^(Present|Absent|Half-day|Half Day|Holiday|Weekly Off|Weekend|WFH)$")
    hours_worked: Decimal = Decimal("0")
    ot_hours: Decimal = Decimal("0")
    remarks: Optional[str] = None


class AttendanceBulkEntryRequest(BaseModel):
    entries: List[AttendanceManualEntry]


class AttendanceBulkEntryResponse(BaseModel):
    saved: int
    items: List[AttendanceRegisterRow]


class AttendanceTodayResponse(BaseModel):
    attendance: Optional[AttendanceSchema] = None
    punches: List[AttendancePunchSchema] = []


class AttendancePageResponse(BaseModel):
    items: List[AttendanceSchema]
    total: int
    page: int
    page_size: int


class RegularizationRequest(BaseModel):
    attendance_id: Optional[int] = None
    date: Optional[date_type] = None
    requested_check_in: Optional[datetime] = None
    requested_check_out: Optional[datetime] = None
    expected_check_in: Optional[datetime] = None
    expected_check_out: Optional[datetime] = None
    reason: str


class RegularizationApproval(BaseModel):
    status: str  # Approved, Rejected
    review_remarks: Optional[str] = None


class RegularizationSchema(BaseModel):
    id: int
    attendance_id: int
    employee_id: int
    requested_check_in: Optional[datetime] = None
    requested_check_out: Optional[datetime] = None
    reason: str
    status: str
    reviewed_at: Optional[datetime] = None
    review_remarks: Optional[str] = None

    class Config:
        from_attributes = True


class AttendanceSummary(BaseModel):
    employee_id: int
    month: int
    year: int
    total_working_days: int
    present_days: int
    absent_days: int
    half_days: int
    leave_days: int
    holiday_days: int
    late_count: int
    overtime_hours: Decimal
