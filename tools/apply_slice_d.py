#!/usr/bin/env python3
"""Apply Phase 10 Slice D fa.json keys (D1/D2/D3). Run: python3 tools/apply_slice_d.py [d1|d2|d3|all]"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FA_PATH = ROOT / "app/localization/locales/fa.json"

# Import D1 from sibling module
sys.path.insert(0, str(ROOT / "tools"))
from admin_fa_slice_d import D1_FA, add_keys, count_hardcoded, load_fa, save_fa  # noqa: E402

# Fix Persian digits → Latin in D1
for k, v in list(D1_FA.items()):
    D1_FA[k] = (
        v.replace("۲", "2")
        .replace("۳", "3")
        .replace("۷", "7")
        .replace("۳۰", "30")
        .replace("۱", "1")
        .replace("۱۵", "15")
    )

D2_MSG: dict[str, str] = {
    "ADMIN_MSG_BROADCAST_TARGETS": "🎯 <b>انتخاب مخاطب</b>\n\nدسته کاربران را برای ارسال انتخاب کنید:",
    "ADMIN_MSG_NO_TARIFFS": "❌ <b>تعرفه‌ای موجود نیست</b>\n\nتعرفه‌ها را در بخش مدیریت تعرفه بسازید.",
    "ADMIN_MSG_TARIFF_FILTER": "📦 <b>ارسال بر اساس تعرفه</b>\n\nتعرفه را برای کاربران با اشتراک فعال انتخاب کنید:",
    "ADMIN_MSG_TARIFF_BTN": "{name} ({count} نفر)",
    "ADMIN_MSG_HISTORY_EMPTY": "📋 <b>تاریخچه ارسال</b>\n\n❌ تاریخچه خالی است.\nاولین ارسال را انجام دهید تا اینجا نمایش داده شود.",
    "ADMIN_MSG_HISTORY_TITLE": "📋 <b>تاریخچه ارسال</b> (صفحه {page}/{pages})\n\n",
    "ADMIN_MSG_HISTORY_LINE": "{emoji} <b>{time}</b>\n📊 ارسال‌شده: {sent}/{total} ({rate}%)\n🎯 مخاطب: {target}\n👤 ادمین: {admin}\n📝 پیام: {preview}\n━━━━━━━━━━━━━━━━━━━━━━━\n",
    "ADMIN_MSG_HISTORY_POLL": "📊 نظرسنجی",
    "ADMIN_MSG_CUSTOM_TITLE": "📝 <b>ارسال بر اساس معیار</b>\n\n📊 <b>فیلترهای موجود:</b>\n\n👥 <b>ثبت‌نام:</b>\n• امروز: {today} نفر\n• هفته: {week} نفر\n• ماه: {month} نفر\n\n💼 <b>فعالیت:</b>\n• فعال امروز: {active_today} نفر\n• غیرفعال 7+ روز: {inactive_week} نفر\n• غیرفعال 30+ روز: {inactive_month} نفر\n\n🔗 <b>منبع:</b>\n• از ارجاع: {referrals} نفر\n• مستقیم: {direct} نفر\n\nمعیار فیلتر را انتخاب کنید:",
    "ADMIN_MSG_CRITERIA_TODAY": "ثبت‌نام امروز",
    "ADMIN_MSG_CRITERIA_WEEK": "ثبت‌نام هفته",
    "ADMIN_MSG_CRITERIA_MONTH": "ثبت‌نام ماه",
    "ADMIN_MSG_CRITERIA_ACTIVE_TODAY": "فعال امروز",
    "ADMIN_MSG_CRITERIA_INACTIVE_WEEK": "غیرفعال 7+ روز",
    "ADMIN_MSG_CRITERIA_INACTIVE_MONTH": "غیرفعال 30+ روز",
    "ADMIN_MSG_CRITERIA_REFERRALS": "از ارجاع",
    "ADMIN_MSG_CRITERIA_DIRECT": "ثبت‌نام مستقیم",
    "ADMIN_MSG_CREATE_BROADCAST": "📨 <b>ایجاد ارسال</b>\n\n🎯 <b>معیار:</b> {target}\n👥 <b>گیرندگان:</b> {count}\n\nمتن پیام را وارد کنید:\n\n<i>HTML پشتیبانی می‌شود</i>",
    "ADMIN_MSG_TARGET_ALL": "همه کاربران",
    "ADMIN_MSG_TARGET_ACTIVE": "با اشتراک فعال",
    "ADMIN_MSG_TARGET_TRIAL": "با اشتراک آزمایشی",
    "ADMIN_MSG_TARGET_NO": "بدون اشتراک",
    "ADMIN_MSG_TARGET_EXPIRING": "اشتراک در حال انقضا",
    "ADMIN_MSG_TARGET_EXPIRED": "اشتراک منقضی",
    "ADMIN_MSG_TARGET_ACTIVE_ZERO": "اشتراک فعال، حجم 0 GB",
    "ADMIN_MSG_TARGET_TRIAL_ZERO": "آزمایشی فعال، حجم 0 GB",
    "ADMIN_MSG_TARGET_TARIFF": "تعرفه «{name}»",
    "ADMIN_MSG_TARGET_TARIFF_ID": "تعرفه #{id}",
    "ADMIN_MSG_CREATE_AUDIENCE": "📨 <b>ایجاد ارسال</b>\n\n🎯 <b>مخاطب:</b> {target}\n👥 <b>گیرندگان:</b> {count}\n\nمتن پیام را وارد کنید:\n\n<i>HTML پشتیبانی می‌شود</i>",
    "ADMIN_MSG_TOO_LONG": "❌ پیام خیلی طولانی است (حداکثر 4000 کاراکتر)",
    "ADMIN_MSG_MEDIA_STEP": "🖼️ <b>افزودن رسانه</b>\n\nمی‌توانید عکس، ویدیو یا سند اضافه کنید.\nیا این مرحله را رد کنید.\n\nنوع رسانه را انتخاب کنید:",
    "ADMIN_MSG_MEDIA_PHOTO": "📷 عکس را برای ارسال بفرستید:",
    "ADMIN_MSG_MEDIA_VIDEO": "🎥 ویدیو را برای ارسال بفرستید:",
    "ADMIN_MSG_MEDIA_DOC": "📄 سند را برای ارسال بفرستید:",
    "ADMIN_MSG_MEDIA_GENERIC": "فایل رسانه را بفرستید:",
    "ADMIN_MSG_MEDIA_SIZE": "<i>حداکثر حجم فایل 50 MB</i>",
    "ADMIN_MSG_MEDIA_WRONG_TYPE": "❌ لطفاً {expected} مطابق راهنما بفرستید.",
    "ADMIN_MSG_MEDIA_ADDED": "🖼️ <b>رسانه اضافه شد</b>\n\n📎 <b>نوع:</b> {media_type}\n✅ فایل ذخیره و آماده ارسال است\n\nبعدی؟",
    "ADMIN_MSG_MEDIA_INFO": "\n🖼️ <b>رسانه:</b> {media_type} اضافه شد",
    "ADMIN_MSG_CHANGE_MEDIA": "🖼️ <b>تغییر رسانه</b>\n\nنوع جدید را انتخاب کنید:",
    "ADMIN_MSG_BUTTONS_TITLE": "📘 <b>انتخاب دکمه‌های اضافی</b>\n\nدکمه‌های پیوست به پیام ارسال را انتخاب کنید:\n\n💰 <b>شارژ موجودی</b> — روش‌های پرداخت\n🤝 <b>همکاری</b> — برنامه ارجاع\n🎫 <b>کد تخفیف</b> — فرم کد\n🔗 <b>اتصال</b> — راهنمای اتصال\n📱 <b>اشتراک</b> — وضعیت اشتراک\n🛠️ <b>پشتیبانی</b> — تماس با پشتیبانی\n\n🏠 دکمه «خانه» پیش‌فرض فعال است؛ می‌توانید غیرفعال کنید.{media_info}\n\nدکمه‌ها را انتخاب و «ادامه» بزنید:",
    "ADMIN_MSG_MEDIA_PHOTO_LABEL": "عکس",
    "ADMIN_MSG_MEDIA_VIDEO_LABEL": "ویدیو",
    "ADMIN_MSG_MEDIA_DOC_LABEL": "سند",
    "ADMIN_MSG_PREVIEW_TITLE": "📨 <b>پیش‌نمایش ارسال</b>\n\n🎯 <b>مخاطب:</b> {target}\n👥 <b>گیرندگان:</b> {count}\n\n📝 <b>پیام:</b>\n{message}{media_info}\n\n{buttons_info}\n\nارسال تأیید شود؟",
    "ADMIN_MSG_PREVIEW_BUTTONS": "📘 <b>دکمه‌ها:</b> {names}",
    "ADMIN_MSG_PREVIEW_NO_BUTTONS": "📘 <b>دکمه‌ها:</b> ندارد",
    "ADMIN_MSG_PREPARE": "📨 <b>آماده‌سازی ارسال...</b>\n\n⏳ بارگذاری فهرست گیرندگان...",
    "ADMIN_MSG_PROGRESS": "📨 <b>ارسال در جریان...</b>\n\n[{bar}] {percent}%\n\n📊 <b>پیشرفت:</b>\n• ارسال‌شده: {sent}\n{blocked_line}• خطا: {failed}\n• پردازش: {processed}/{total}\n\n⏳ دیالوگ را نبندید...",
    "ADMIN_MSG_PROGRESS_BLOCKED": "• مسدود کردند: {blocked}\n",
    "ADMIN_MSG_DONE": "✅ <b>ارسال تمام شد!</b>\n\n📊 <b>نتیجه:</b>\n• ارسال‌شده: {sent}\n{blocked_line}• ناموفق: {failed}\n• کل کاربران: {total}\n• موفقیت: {rate}%{media_info}\n\n<b>ادمین:</b> {admin}",
    "ADMIN_MSG_NOT_FOUND": "❌ پیام یافت نشد",
    "ADMIN_MSG_PINNED_MEDIA_LABEL_PHOTO": "عکس",
    "ADMIN_MSG_PINNED_MEDIA_LABEL_VIDEO": "ویدیو",
    "ADMIN_MSG_TARGET_ZERO": "اشتراک، حجم 0 GB",
    "ADMIN_MSG_TARGET_TARIFF_BY_ID": "بر اساس تعرفه #{id}",
    "ADMIN_MSG_TARGET_CUSTOM_TODAY": "ثبت‌نام امروز",
    "ADMIN_MSG_TARGET_CUSTOM_WEEK": "ثبت‌نام هفته",
    "ADMIN_MSG_TARGET_CUSTOM_MONTH": "ثبت‌نام ماه",
    "ADMIN_MSG_TARGET_CUSTOM_ACTIVE": "فعال امروز",
    "ADMIN_MSG_TARGET_CUSTOM_INACTIVE_WEEK": "غیرفعال 7+ روز",
    "ADMIN_MSG_TARGET_CUSTOM_INACTIVE_MONTH": "غیرفعال 30+ روز",
    "ADMIN_MSG_TARGET_CUSTOM_REFERRALS": "از ارجاع",
    "ADMIN_MSG_TARGET_CUSTOM_DIRECT": "مستقیم",
}

D3_MON: dict[str, str] = {
    "ADMIN_MON_TOGGLE_ON": "🟢 روشن",
    "ADMIN_MON_TOGGLE_OFF": "🔴 خاموش",
    "ADMIN_MON_NOTIFY_TITLE": "🔔 <b>اعلان به کاربران</b>\n\n• لغو کانال: {trial}\n• 1 روز پس از انقضا: {exp1}\n• 2-3 روز (تخفیف {p2}% / {h2} س): {wave2}\n• {d3} روز (تخفیف {p3}% / {h3} س): {wave3}",
    "ADMIN_MON_BTN_TRIAL": "{status} • لغو کانال",
    "ADMIN_MON_BTN_TEST_TRIAL": "🧪 تست: لغو کانال",
    "ADMIN_MON_BTN_EXP1": "{status} • 1 روز پس از انقضا",
    "ADMIN_MON_BTN_TEST_EXP1": "🧪 تست: 1 روز پس از انقضا",
    "ADMIN_MON_BTN_WAVE2": "{status} • 2-3 روز با تخفیف",
    "ADMIN_MON_BTN_TEST_WAVE2": "🧪 تست: تخفیف روز 2-3",
    "ADMIN_MON_BTN_EDIT_P2": "✏️ تخفیف 2-3 روز: {percent}%",
    "ADMIN_MON_BTN_EDIT_H2": "⏱️ مدت تخفیف 2-3 روز: {hours} س",
    "ADMIN_MON_BTN_WAVE3": "{status} • {days} روز با تخفیف",
    "ADMIN_MON_BTN_TEST_WAVE3": "🧪 تست: تخفیف پس از روزها",
    "ADMIN_MON_BTN_EDIT_P3": "✏️ تخفیف {days} روز: {percent}%",
    "ADMIN_MON_BTN_EDIT_H3": "⏱️ مدت تخفیف {days} روز: {hours} س",
    "ADMIN_MON_BTN_THRESHOLD": "📆 آستانه اعلان: {days} روز",
    "ADMIN_MON_BTN_TEST_ALL": "🧪 ارسال همه تست‌ها",
    "ADMIN_MON_PREVIEW_HEADER": "🧪 <b>اعلان تست مانیتورینگ</b>\n\n",
    "ADMIN_MON_PREVIEW_FOOTER": "\n\n<i>فقط برای بررسی ظاهر به شما ارسال شد.</i>",
    "ADMIN_MON_PREVIEW_DISCOUNT_BTN": "🎁 دریافت تخفیف",
    "ADMIN_MON_MENU": "🔍 <b>سیستم مانیتورینگ</b>\n\n📊 <b>وضعیت:</b> {running}\n🕐 <b>آخرین به‌روزرسانی:</b> {last}\n⚙️ <b>فاصله بررسی:</b> {interval} دقیقه\n\n📈 <b>آمار 24 ساعت:</b>\n• کل رویدادها: {events}\n• موفق: {success}\n• خطا: {errors}\n• موفقیت: {rate}%\n\n🔧 عملیات را انتخاب کنید:",
    "ADMIN_MON_RUNNING": "🟢 در حال اجرا",
    "ADMIN_MON_STOPPED": "🔴 متوقف",
    "ADMIN_MON_NEVER": "هرگز",
    "ADMIN_MON_DATA_ERR": "❌ خطا در دریافت داده",
    "ADMIN_MON_SETTINGS": "⚙️ <b>تنظیمات مانیتورینگ</b>\n\n🔔 <b>اعلان کاربران:</b> {global}\n• تخفیف 2-3 روز: {p2}%\n• تخفیف پس از {d3} روز: {p3}%\n\nبخش را برای تنظیم انتخاب کنید.",
    "ADMIN_MON_GLOBAL_ON": "🟢 فعال",
    "ADMIN_MON_GLOBAL_OFF": "🔴 غیرفعال",
    "ADMIN_MON_BTN_NOTIFY": "🔔 اعلان کاربران",
    "ADMIN_MON_SETTINGS_ERR": "❌ باز کردن تنظیمات ناموفق",
    "ADMIN_MON_NOTIFY_ERR": "❌ بارگذاری تنظیمات ناموفق",
    "ADMIN_MON_TOGGLED_ON": "✅ فعال شد",
    "ADMIN_MON_TOGGLED_OFF": "⏸️ غیرفعال شد",
    "ADMIN_MON_PREVIEW_SENT": "✅ نمونه ارسال شد",
    "ADMIN_MON_PREVIEW_FAIL": "❌ ارسال تست ناموفق",
    "ADMIN_MON_ALL_SENT": "✅ همه تست‌ها ارسال شد",
    "ADMIN_MON_ALL_FAIL": "❌ ارسال تست‌ها ناموفق",
    "ADMIN_MON_ALREADY_RUNNING": "ℹ️ مانیتورینگ از قبل اجراست",
    "ADMIN_MON_STARTED": "✅ مانیتورینگ شروع شد!",
    "ADMIN_MON_START_ERR": "❌ خطا در شروع: {error}",
    "ADMIN_MON_ALREADY_STOPPED": "ℹ️ مانیتورینگ از قبل متوقف است",
    "ADMIN_MON_STOPPED_MSG": "⏹️ مانیتورینگ متوقف شد!",
    "ADMIN_MON_STOP_ERR": "❌ خطا در توقف: {error}",
    "ADMIN_MON_FORCE_CHECK": "⏳ بررسی اشتراک‌ها...",
    "ADMIN_MON_FORCE_DONE": "✅ <b>بررسی اجباری تمام شد</b>\n\n📊 <b>نتایج:</b>\n• منقضی: {expired}\n• در حال انقضا: {expiring}\n• آماده خودپرداخت: {autopay}\n\n🕐 <b>زمان:</b> {time}\n\n«بازگشت» برای منو مانیتورینگ.",
    "ADMIN_MON_FORCE_ERR": "❌ خطا در بررسی: {error}",
    "ADMIN_MON_TRAFFIC_DISABLED": "⚠️ مانیتورینگ حجم غیرفعال است\nTRAFFIC_FAST_CHECK_ENABLED=true در .env",
    "ADMIN_MON_TRAFFIC_CHECK": "⏳ بررسی حجم (دلتا)...",
    "ADMIN_MON_TRAFFIC_DONE": "📊 <b>بررسی حجم تمام شد</b>\n\n🔍 <b>نتایج (دلتا):</b>\n• تجاوز در بازه: {count}\n• آستانه دلتا: {threshold} GB\n• سن snapshot: {age:.1f} دقیقه\n\n🕐 <b>زمان:</b> {time}",
    "ADMIN_MON_TRAFFIC_VIOLATIONS": "\n⚠️ <b>تجاوز دلتا:</b>\n",
    "ADMIN_MON_TRAFFIC_VIOLATION_LINE": "• {name}: +{gb:.1f} GB\n",
    "ADMIN_MON_TRAFFIC_MORE": "... و {count} مورد دیگر\n",
    "ADMIN_MON_TRAFFIC_NOTIFY": "\n📨 اعلان‌ها ارسال شد (با کولداون)",
    "ADMIN_MON_TRAFFIC_OK": "\n✅ تجاوزی یافت نشد",
    "ADMIN_MON_TRAFFIC_ERR": "❌ خطا: {error}",
    "ADMIN_MON_LOGS_EMPTY": "📋 <b>لاگ مانیتورینگ خالی است</b>\n\nهنوز بررسی انجام نشده.",
    "ADMIN_MON_LOGS_TITLE": "📋 <b>لاگ مانیتورینگ</b> (صفحه {page}/{pages})\n\n",
    "ADMIN_MON_LOGS_LINE": "{icon} <code>{time}</code> {event}\n   📄 {message}\n\n",
    "ADMIN_MON_LOGS_STATS": "📊 <b>آمار کلی:</b>\n• کل رویدادها: {total}\n• موفق: {success}\n• خطا: {failed}\n• موفقیت: {rate}%",
    "ADMIN_MON_LOGS_ERR": "❌ خطا در دریافت لاگ",
    "ADMIN_MON_LOGS_CLEARED": "🗑️ {count} رکورد لاگ حذف شد",
    "ADMIN_MON_LOGS_ALREADY_EMPTY": "ℹ️ لاگ از قبل خالی است",
    "ADMIN_MON_LOGS_CLEAR_ERR": "❌ خطا در پاکسازی: {error}",
    "ADMIN_MON_TEST_MSG": "🧪 <b>اعلان تست مانیتورینگ</b>\n\nپیام تست سیستم اعلان.\n\n📊 <b>وضعیت:</b>\n• مانیتورینگ: {running}\n• اعلان‌ها: {notify}\n• زمان تست: {time}\n\n✅ دریافت این پیام یعنی سیستم اعلان سالم است!",
    "ADMIN_MON_TEST_SENT": "✅ اعلان تست ارسال شد!",
    "ADMIN_MON_TEST_ERR": "❌ خطا در ارسال: {error}",
    "ADMIN_MON_STATS_TITLE": "📊 <b>آمار مانیتورینگ</b>\n\n📱 <b>اشتراک‌ها:</b>\n• کل: {total}\n• فعال: {active}\n• آزمایشی: {trial}\n• پولی: {paid}\n\n📈 <b>امروز:</b>\n• موفق: {today_ok}\n• خطا: {today_err}\n• موفقیت: {today_rate}%\n\n📊 <b>هفته:</b>\n• رویدادها: {week_total}\n• موفق: {week_ok}\n• خطا: {week_err}\n• موفقیت: {week_rate}%\n\n🔧 <b>سیستم:</b>\n• فاصله: {interval} دقیقه\n• اعلان: {notify_toggle}\n• خودپرداخت: {autopay_days} روز",
    "ADMIN_MON_NALOGO_SECTION": "\n🧾 <b>چک NaloGO:</b>\n• سرویس: {running}\n• در صف: {queue} چک",
    "ADMIN_MON_NALOGO_AMOUNT": "\n• مبلغ: {amount:,.2f} ₽",
    "ADMIN_MON_NALOGO_PENDING": "\n⚠️ <b>نیاز به بررسی: {count} ({amount:,.2f} ₽)</b>",
    "ADMIN_MON_BTN_SEND_NALOGO": "🧾 ارسال ({count})",
    "ADMIN_MON_BTN_CHECK_NALOGO": "⚠️ بررسی ({count})",
    "ADMIN_MON_BTN_RECONCILE": "📊 تطبیق چک‌ها",
    "ADMIN_MON_STATS_ERR": "❌ خطا در آمار: {error}",
    "ADMIN_MON_NALOGO_PROCESSING": "🔄 پردازش صف چک...",
    "ADMIN_MON_NALOGO_DONE": "✅ پردازش: {processed} چک",
    "ADMIN_MON_NALOGO_REMAINING": "\n⏳ باقی‌مانده: {remaining}",
    "ADMIN_MON_NALOGO_UNAVAILABLE": "⚠️ سرویس nalog.ru در دسترس نیست\n⏳ در صف: {remaining} چک",
    "ADMIN_MON_NALOGO_EMPTY": "📭 صف خالی است",
    "ADMIN_MON_NALOGO_NO_PENDING": "✅ چکی برای بررسی نیست",
    "ADMIN_MON_NALOGO_PENDING_TITLE": "⚠️ <b>چک‌های نیازمند بررسی: {count}</b>\n\nدر lknpd.nalog.ru بررسی کنید.\n\n",
    "ADMIN_MON_NALOGO_PENDING_LINE": "<b>{i}. {amount:,.2f} ₽</b>\n   📅 {date}\n   🆔 <code>{id}...</code>\n{error}\n",
    "ADMIN_MON_NALOGO_MORE": "\n... و {count} چک دیگر",
    "ADMIN_MON_BTN_VERIFIED": "✅ ایجاد شد ({i})",
    "ADMIN_MON_BTN_RETRY": "🔄 ارسال ({i})",
    "ADMIN_MON_BTN_CLEAR_PENDING": "🗑 پاک کردن همه (بررسی شد)",
    "ADMIN_MON_VERIFIED_OK": "✅ چک ایجادشده علامت خورد",
    "ADMIN_MON_NOT_FOUND": "❌ چک یافت نشد",
    "ADMIN_MON_RETRYING": "🔄 در حال ارسال چک...",
    "ADMIN_MON_RETRY_OK": "✅ چک ایجاد شد: {uuid}",
    "ADMIN_MON_RETRY_FAIL": "❌ ایجاد چک ناموفق",
    "ADMIN_MON_CLEARED": "✅ {count} چک پاک شد",
    "ADMIN_MON_QUEUE_CLEARED": "✅ صف بررسی پاک شد",
    "ADMIN_MON_TRAFFIC_SETTINGS": "⚙️ <b>تنظیمات مانیتورینگ حجم</b>\n\n<b>بررسی سریع:</b> {fast}\n• فاصله: {fast_interval} دقیقه\n• آستانه دلتا: {fast_threshold} GB\n\n<b>بررسی روزانه:</b> {daily}\n• زمان: {daily_time} UTC\n• آستانه: {daily_threshold} GB\n\n<b>عمومی:</b>\n• کولداون اعلان: {cooldown} دقیقه\n",
    "ADMIN_MON_TRAFFIC_MONITORED": "• فقط نودها: {count}\n",
    "ADMIN_MON_TRAFFIC_IGNORED": "• نادیده: {count} نود\n",
    "ADMIN_MON_TRAFFIC_EXCLUDED": "• کاربران مستثنی: {count}\n",
    "ADMIN_MON_BTN_FAST": "{toggle} بررسی سریع",
    "ADMIN_MON_BTN_DAILY": "{toggle} بررسی روزانه",
    "ADMIN_MON_BTN_FAST_INTERVAL": "⏱ فاصله: {minutes} دقیقه",
    "ADMIN_MON_BTN_FAST_THRESHOLD": "📊 آستانه دلتا: {gb} GB",
    "ADMIN_MON_BTN_DAILY_TIME": "🕐 زمان: {time}",
    "ADMIN_MON_BTN_DAILY_THRESHOLD": "📈 آستانه روزانه: {gb} GB",
    "ADMIN_MON_BTN_COOLDOWN": "⏳ کولداون: {minutes} دقیقه",
    "ADMIN_MON_TRAFFIC_LOAD_ERR": "❌ خطا در بارگذاری تنظیمات",
    "ADMIN_MON_TRAFFIC_TOGGLE_ERR": "❌ خطا",
    "ADMIN_MON_PROMPT_FAST_INTERVAL": "⏱ فاصله بررسی سریع را به دقیقه وارد کنید (حداقل 1):",
    "ADMIN_MON_PROMPT_FAST_THRESHOLD": "📊 آستانه دلتا حجم را به GB وارد کنید (مثلاً 5.0):",
    "ADMIN_MON_PROMPT_DAILY_TIME": "🕐 زمان بررسی روزانه HH:MM (UTC):\nمثال: 00:00, 03:00, 12:30",
    "ADMIN_MON_PROMPT_DAILY_THRESHOLD": "📈 آستانه روزانه حجم را به GB وارد کنید (مثلاً 50.0):",
    "ADMIN_MON_PROMPT_COOLDOWN": "⏳ کولداون اعلان را به دقیقه وارد کنید (حداقل 1):",
    "ADMIN_MON_CONTEXT_LOST": "ℹ️ زمینه از دست رفت؛ از منو دوباره تلاش کنید.",
    "ADMIN_MON_VALUE_SAVED": "✅ تنظیم ذخیره شد!",
    "ADMIN_MON_SAVE_ERR": "❌ خطا در ذخیره: {error}",
    "ADMIN_MON_CMD_STATUS": "🔍 <b>وضعیت سریع مانیتورینگ</b>\n\n📊 <b>وضعیت:</b> {running}\n📈 <b>رویداد 24س:</b> {events}\n✅ <b>موفقیت:</b> {rate}%\n\nبرای جزئیات از پنل ادمین استفاده کنید.",
    "ADMIN_MON_CMD_ERR": "❌ خطا: {error}",
    "ADMIN_MON_PERCENT_RANGE": "❌ درصد تخفیف باید 0 تا 100 باشد.",
    "ADMIN_MON_HOURS_RANGE": "❌ ساعت باید 1 تا 168 باشد.",
    "ADMIN_MON_DAYS_MIN": "❌ حداقل 2 روز.",
    "ADMIN_MON_PROMPT_SECOND_PERCENT": "درصد تخفیف اعلان 2-3 روز (0-100):",
    "ADMIN_MON_PROMPT_SECOND_HOURS": "مدت تخفیف به ساعت (1-168):",
    "ADMIN_MON_PROMPT_THIRD_PERCENT": "درصد تخفیف دیرتر (0-100):",
    "ADMIN_MON_PROMPT_THIRD_HOURS": "مدت تخفیف به ساعت (1-168):",
    "ADMIN_MON_PROMPT_THIRD_DAYS": "چند روز پس از انقضا اعلان ارسال شود؟ (حداقل 2):",
    "ADMIN_MON_TOGGLE_ENABLED": "✅ فعال",
    "ADMIN_MON_TOGGLE_DISABLED": "⏸️ غیرفعال",
    "ADMIN_MON_BACK_TRAFFIC": "⬅️ به تنظیمات حجم",
    "ADMIN_MON_RECONCILE_NO_LOG": "❌ <b>فایل لاگ یافت نشد</b>\n\nمسیر: <code>{path}</code>\n\n<i>پس از اولین پرداخت موفق ظاهر می‌شود.</i>",
    "ADMIN_MON_RECONCILE_READ_ERR": "❌ <b>خطا در خواندن لاگ</b>\n\n{error}",
    "ADMIN_MON_RECONCILE_TITLE": "📋 <b>تطبیق لاگ</b>\n\n📦 <b>کل پرداخت‌ها:</b> {payments}\n🧾 <b>چک ایجادشده:</b> {receipts}\n\n",
    "ADMIN_MON_RECONCILE_ALL_OK": "✅ <b>همه پرداخت‌ها چک دارند!</b>",
    "ADMIN_MON_RECONCILE_MISSING": "⚠️ <b>بدون چک:</b> {count} پرداخت به {amount:,.2f} ₽\n\n",
    "ADMIN_MON_RECONCILE_DATE_LINE": "• <b>{date}:</b> {count} مورد به {amount:,.2f} ₽\n",
    "ADMIN_MON_RECONCILE_MORE_DAYS": "\n<i>...و {count} روز دیگر</i>",
    "ADMIN_MON_RECONCILE_DETAILS_TITLE": "📄 <b>پرداخت بدون چک ({count})</b>\n\n",
    "ADMIN_MON_RECONCILE_DETAIL_LINE": "• <b>{date} {time}</b>\n  User: {user} | {amount:.0f}₽\n  <code>{payment_id}...</code>\n\n",
    "ADMIN_MON_RECONCILE_MORE": "<i>...و {count} پرداخت دیگر</i>",
    "ADMIN_MON_LINK_DONE": "🔗 <b>پیوند تمام شد</b>\n\nکل تراکنش: {total}\nچک در NaloGO: {incomes}\nپیوندشده: <b>{linked}</b>\nناموفق: {failed}",
    "ADMIN_MON_LINK_NONE": "✅ تراکنش قدیمی برای پیوند نیست",
    "ADMIN_MON_LINK_ERR": "❌ خطا: {error}",
    "ADMIN_MON_LOADING": "🔄 بارگذاری چک از NaloGO...",
    "ADMIN_MON_NALOGO_FETCH_FAIL": "❌ دریافت چک از NaloGO ناموفق",
    "ADMIN_MON_ANALYZING": "🔄 تحلیل لاگ پرداخت...",
    "ADMIN_MON_LOADING_DETAILS": "🔄 بارگذاری جزئیات...",
    "ADMIN_MON_LOG_FILE_MISSING": "❌ فایل لاگ یافت نشد",
}


def apply_fa_keys(which: str) -> tuple[int, int]:
    fa = load_fa()
    before = len(fa)
    added = 0
    if which in ("d1", "all"):
        added += add_keys(fa, D1_FA)
    if which in ("d2", "all"):
        added += add_keys(fa, D2_MSG)
    if which in ("d3", "all"):
        added += add_keys(fa, D3_MON)
    save_fa(fa)
    return before, len(fa) - before


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    before, new = apply_fa_keys(which)
    print(f"fa.json: {before} keys, +{new} new for {which}")


if __name__ == "__main__":
    main()
