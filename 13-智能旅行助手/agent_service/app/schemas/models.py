"""Pydantic 数据模型：既是内部接口契约，也是 LLM 结构化输出的 schema。"""

from datetime import date

from pydantic import BaseModel, Field, model_validator


class TripPlanRequest(BaseModel):
    city: str = Field(min_length=1, max_length=32)
    start_date: date
    end_date: date
    days: int = Field(ge=1, le=15)
    preferences: str = Field(default="", max_length=200)
    budget_level: str = Field(default="中等", max_length=16)
    transportation: str = Field(default="公共交通", max_length=16)
    accommodation: str = Field(default="经济型酒店", max_length=32)

    @model_validator(mode="after")
    def check_dates(self) -> "TripPlanRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date 不能早于 start_date")
        return self


class Attraction(BaseModel):
    name: str
    address: str = ""
    visit_duration: str = ""
    description: str = ""
    ticket_price: float = 0.0
    latitude: float | None = None
    longitude: float | None = None
    image_url: str | None = None


class WeatherInfo(BaseModel):
    date: str
    day_weather: str = ""
    night_weather: str = ""
    day_temp: int = 0
    night_temp: int = 0
    wind: str = ""


class Hotel(BaseModel):
    name: str
    address: str = ""
    price_per_night: float = 0.0
    rating: str = ""


class Meal(BaseModel):
    type: str
    name: str
    description: str = ""
    estimated_cost: float = 0.0


class DayPlan(BaseModel):
    day_index: int
    date: str
    theme: str = ""
    attractions: list[Attraction] = Field(default_factory=list)
    meals: list[Meal] = Field(default_factory=list)
    hotel: Hotel | None = None
    transportation: str = ""
    transportation_cost: float = 0.0
    notes: str = ""


class TripPlanDraft(BaseModel):
    """LLM 只产出明细与单价；总预算由 Java 用整数分精确求和。"""

    city: str
    start_date: str
    end_date: str
    summary: str = ""
    days: list[DayPlan] = Field(default_factory=list)
    weather_info: list[WeatherInfo] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
