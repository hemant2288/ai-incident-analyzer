from app.config import settings


def _service_revenue_weight(service_name: str) -> float:
    weights = {
        "payment-api": settings.service_revenue_weight_payment_api,
        "user-service": settings.service_revenue_weight_user_service,
    }
    return weights.get(service_name, settings.service_revenue_weight_default)


def calculate_financial_loss(
    service_name: str,
    downtime_minutes: float,
    company_hourly_revenue: float,
) -> dict[str, float | str]:
    safe_downtime = max(float(downtime_minutes or 0), 0.0)
    safe_revenue = max(float(company_hourly_revenue or settings.company_hourly_revenue), 0.0)

    downtime_hours = safe_downtime / 60.0
    weight = _service_revenue_weight(service_name)

    direct_lost_revenue = round(safe_revenue * downtime_hours * weight, 2)
    engineering_triage_cost = round(
        settings.engineering_hourly_cost * max(downtime_hours, 0.25),
        2,
    )
    total_estimated_loss = round(direct_lost_revenue + engineering_triage_cost, 2)

    return {
        "service_name": service_name,
        "downtime_minutes": safe_downtime,
        "downtime_hours": round(downtime_hours, 2),
        "company_hourly_revenue": safe_revenue,
        "service_revenue_weight": weight,
        "direct_lost_revenue_usd": direct_lost_revenue,
        "engineering_triage_cost_usd": engineering_triage_cost,
        "total_estimated_loss_usd": total_estimated_loss,
        "summary": (
            f"Estimated Loss: ${total_estimated_loss:,.0f} "
            f"(Revenue: ${direct_lost_revenue:,.0f} + "
            f"Engineering: ${engineering_triage_cost:,.0f} over "
            f"{safe_downtime:.0f} min downtime)"
        ),
    }
