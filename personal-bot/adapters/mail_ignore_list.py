"""
Список отправителей/доменов, скрываемых из дневной сводки почты — простое
правило по домену, не LLM (пользователь явно выбрал этот подход над
классификацией через Claude — быстрее, бесплатно, предсказуемо).

Применяется ТОЛЬКО к дневной сводке (handlers/mail_alerts.send_daily_mail_summary).
Срочные алерты не нуждаются в этом списке — urgency_classifier уже решает,
показывать письмо или нет, по смыслу, а не по отправителю. Поиск по запросу
(handlers/mail_search.py) тоже не фильтруется — если пользователь явно ищет
письмо, скрывать результаты по этому списку было бы неверно.

Обычный JSON-файл (mail_ignore_list.json, gitignored, как urgency_rules.json)
— список доменов, редактируется вручную или через add_ignored_domain().
"""

import json
import os

_IGNORE_LIST_PATH = os.path.join(os.path.dirname(__file__), "..", "mail_ignore_list.json")

# Стартовый список — то, что попало в дневную сводку 2026-08-28 и было явно
# названо пользователем как ненужный шум (скриншот с Vercel/Google-входом/
# Skroutz/eBay-трекингом). Файл на диске (если существует) полностью
# перекрывает этот список при первом же add/remove — это только дефолт для
# первого запуска, когда файла ещё нет.
#
# "google.com" целиком, а не только accounts.google.com — реальный
# отправитель этих уведомлений noreply-accounts@google.com, домен которого
# после разбора _extract_domain — просто "google.com" (поддомен теряется,
# т.к. это часть адреса до @, а не до .com). Google.com сам по себе не
# рассылает других непрочитанных писем пользователю, так что риска скрыть
# что-то нужное этим доменом нет.
_DEFAULT_IGNORED_DOMAINS = [
    "vercel.com",
    "google.com",  # "Вы передали данные аккаунта Google в сервис..."
    "skroutz.gr",
    "ebay.com",
]


def _load() -> list[str]:
    if not os.path.exists(_IGNORE_LIST_PATH):
        _save(_DEFAULT_IGNORED_DOMAINS)
        return list(_DEFAULT_IGNORED_DOMAINS)
    try:
        with open(_IGNORE_LIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return list(_DEFAULT_IGNORED_DOMAINS)


def _save(domains: list[str]) -> None:
    with open(_IGNORE_LIST_PATH, "w", encoding="utf-8") as f:
        json.dump(domains, f, ensure_ascii=False, indent=2)


def _extract_domain(sender: str) -> str:
    """Из "Vercel <notifications@vercel.com>" достаёт "vercel.com". Из голого
    адреса без имени (уже просто email) — тоже работает."""
    if "@" not in sender:
        return ""
    email_part = sender.split("<")[-1].rstrip(">")
    return email_part.split("@")[-1].strip().lower()


def is_ignored(sender: str) -> bool:
    """True, если домен отправителя (или его часть — noreply-accounts.google.com
    матчит accounts.google.com) в списке игнора."""
    domain = _extract_domain(sender)
    if not domain:
        return False
    ignored = _load()
    return any(domain == d or domain.endswith(f".{d}") for d in ignored)


def add_ignored_domain(domain: str) -> None:
    domains = _load()
    domain = domain.strip().lower()
    if domain not in domains:
        domains.append(domain)
        _save(domains)


def get_ignored_domains() -> list[str]:
    return _load()
