from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator,field_validator

Divisor = Literal['working_days','calendar_days','fixed_26','fixed_30']


class ComponentTreatment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prorate: bool
    lop: bool


class PayrollPolicyRules(BaseModel):
    model_config = ConfigDict(extra='forbid')
    charge_weekly_off: bool = False
    charge_holidays: bool = False
    sandwich_enabled: bool = False
    missing_attendance: Literal['block','payable','lop'] = 'block'
    leave_conflict: Literal['block','paid_wins','unpaid_wins'] = 'block'
    lop_divisor: Divisor = 'working_days'
    proration_divisor: Divisor = 'calendar_days'
    proration_basis: Literal['calendar_days','working_days'] = 'calendar_days'
    use_component_flags: bool = True
    components: dict[str,ComponentTreatment] = Field(default_factory=lambda:{
        'basic': ComponentTreatment(prorate=True,lop=True),
        'hra': ComponentTreatment(prorate=True,lop=True),
        'other_allowances': ComponentTreatment(prorate=True,lop=True),
        'incentives': ComponentTreatment(prorate=False,lop=False),
        'reimbursements': ComponentTreatment(prorate=False,lop=False),
    })

    @field_validator('components',mode='before')
    @classmethod
    def normalize_codes(cls,value):
        if not isinstance(value,dict):return value
        result={}
        for key,treatment in value.items():
            code=str(key).strip().lower()
            if not code or len(code)>100 or code in result:raise ValueError('Component codes must be nonempty, unique ignoring case, and at most 100 characters')
            result[code]=treatment
        return result

    @model_validator(mode='after')
    def complete_mapping(self):
        required={'basic','hra','other_allowances','incentives','reimbursements'}
        if not required.issubset(self.components):
            raise ValueError('Configure proration and LOP treatment for every core earning, incentives and reimbursements')
        if len(self.components)>100:raise ValueError('At most 100 component mappings are supported')
        return self


class PayrollPolicyCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    effective_from: date
    reason: str = Field(min_length=3,max_length=1000)
    rules: PayrollPolicyRules = Field(default_factory=PayrollPolicyRules)

    @model_validator(mode='after')
    def month_boundary(self):
        if self.effective_from.day != 1:raise ValueError('Payroll policy changes take effect on the first day of a month')
        if not self.reason.strip():raise ValueError('A policy change reason is required')
        return self
