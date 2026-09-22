from decimal import Decimal, InvalidOperation
from django.db import transaction
from rest_framework.exceptions import ValidationError
from .models import RiskEvaluation

DEFAULT_LIKELIHOOD=[{"value":1,"label":"Rare"},{"value":2,"label":"Unlikely"},{"value":3,"label":"Possible"},{"value":4,"label":"Likely"},{"value":5,"label":"Almost certain"}]
DEFAULT_IMPACT=[{"value":1,"label":"Insignificant"},{"value":2,"label":"Minor"},{"value":3,"label":"Moderate"},{"value":4,"label":"Major"},{"value":5,"label":"Severe"}]
DEFAULT_THRESHOLDS=[{"min":1,"max":4,"level":"low"},{"min":5,"max":9,"level":"medium"},{"min":10,"max":16,"level":"high"},{"min":17,"max":25,"level":"critical"}]

def methodology_defaults(): return {"likelihood_scale":DEFAULT_LIKELIHOOD,"impact_scale":DEFAULT_IMPACT,"thresholds":DEFAULT_THRESHOLDS,"formula":"product"}

def _decimal(value,name):
    try: return Decimal(str(value))
    except (InvalidOperation,TypeError,ValueError) as exc: raise ValidationError({name:"A numeric value is required."}) from exc

def calculate_score(methodology,likelihood,impact):
    l=_decimal(likelihood,"likelihood");i=_decimal(impact,"impact")
    if methodology.formula!="product": raise ValidationError({"methodology":"Only product formula is implemented in Sprint 3."})
    score=l*i
    level="unclassified"
    for row in methodology.thresholds or []:
        if Decimal(str(row.get("min",0)))<=score<=Decimal(str(row.get("max",0))): level=str(row.get("level") or level);break
    return score,level

@transaction.atomic
def evaluate_risk(*,risk,methodology,evaluation_type,likelihood,impact,user,rationale=""):
    if methodology.tenant_id!=risk.tenant_id: raise ValidationError({"methodology":"Methodology must belong to the same tenant."})
    score,level=calculate_score(methodology,likelihood,impact)
    return RiskEvaluation.objects.create(risk=risk,methodology=methodology,evaluation_type=evaluation_type,likelihood=likelihood,impact=impact,score=score,level=level,evaluated_by=user,rationale=rationale)

def latest_evaluations(risk):
    result={}
    for row in risk.evaluations.select_related("methodology","evaluated_by").order_by("-evaluated_at","-created_at"):
        result.setdefault(row.evaluation_type,row)
    return result
