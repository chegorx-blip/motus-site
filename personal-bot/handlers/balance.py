"""
Проверка трат на Oracle Cloud за текущий календарный месяц.

Использует официальный oci SDK с ключом API, настроенным на сервере в
~/.oci/config (не в репозитории — секрет, привязан к конкретной машине,
см. docs/immich-deployment-plan.md в project1-clone про контекст, зачем
это вообще понадобилось: планировался self-hosted Immich на этом же VPS,
и нужно было следить, чтобы апгрейд ресурсов не вывел из Always Free).

Триггерные фразы для классификатора: "баланс", "сколько потратил на
oracle", "траты на сервер" и т.п. — см. classifier.py, тип "balance".
"""

from datetime import datetime, timedelta, timezone

import oci

_OCI_CONFIG_PATH = "/home/ubuntu/.oci/config"


def get_oracle_spend_this_month() -> str:
    """Возвращает готовую строку для ответа пользователю в Telegram."""
    try:
        config = oci.config.from_file(_OCI_CONFIG_PATH)
        tenancy_id = config["tenancy"]
        usage_client = oci.usage_api.UsageapiClient(config)

        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        details = oci.usage_api.models.RequestSummarizedUsagesDetails(
            tenant_id=tenancy_id,
            time_usage_started=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            time_usage_ended=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            granularity="MONTHLY",
        )
        resp = usage_client.request_summarized_usages(details)

        items = [item for item in resp.data.items if item.computed_amount]
        total = sum(item.computed_amount for item in items)
        currency = items[0].currency if items else "EUR"
        month_name = now.strftime("%B %Y")

        if not items or total == 0:
            return (
                f"💰 Расходы на Oracle Cloud за {month_name}: 0.00 {currency}\n"
                f"Полностью в рамках бесплатного тарифа (Always Free)."
            )

        lines = [f"💰 Расходы на Oracle Cloud за {month_name}:"]
        for item in sorted(items, key=lambda i: -i.computed_amount):
            service = item.service or "Прочее"
            lines.append(f"  • {service}: {item.computed_amount:.2f} {currency}")
        lines.append(f"Итого: {total:.2f} {currency}")
        return "\n".join(lines)

    except Exception as exc:  # noqa: BLE001 — любая ошибка API должна дойти до пользователя текстом, не уронить бота
        return f"⚠️ Не удалось получить данные о балансе Oracle Cloud: {exc}"
