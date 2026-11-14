import re
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from .recurrence import local_instant

class Message(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    channel: Literal['whatsapp','email']
    recipient: str=Field(min_length=3,max_length=254)
    name: str=Field(default='',max_length=160)
    subject: str=Field(default='',max_length=240)
    body: str=Field(min_length=1,max_length=10000)
    scheduled_local: str
    recurrence: Literal['once','daily','weekdays','weekly','monthly','yearly']='once'
    weekdays: list[int]=Field(default_factory=list,max_length=7)
    end_date: str|None=None
    draft: bool=False
    consent: bool=Field(default=False, strict=True)

    @model_validator(mode='after')
    def validate_fields(self):
        if '\n' in self.subject or '\r' in self.subject: raise ValueError('Assunto inválido.')
        if self.channel=='whatsapp':
            self.recipient=re.sub(r'[ ()-]','',self.recipient)
            if not re.fullmatch(r'\+[1-9]\d{6,14}',self.recipient): raise ValueError('Use telefone internacional, por exemplo +12025550123.')
        else:
            if not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+',self.recipient): raise ValueError('Email inválido; apenas um destinatário.')
            if not self.subject: raise ValueError('O email precisa de assunto.')
        local_instant(self.scheduled_local)
        if self.end_date:
            date.fromisoformat(self.end_date)
            if self.end_date < datetime.fromisoformat(self.scheduled_local).date().isoformat(): raise ValueError('Data final anterior ao início.')
        if self.recurrence=='weekdays' and (not self.weekdays or any(type(x)!=int or x<0 or x>6 for x in self.weekdays)):
            raise ValueError('Selecione dias da semana válidos.')
        self.weekdays=sorted(set(self.weekdays))
        return self
