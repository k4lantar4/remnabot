import json
from pathlib import Path

FA = Path('app/localization/locales/fa.json')

REQUIRED = (
    'MY_SUB_LIST_TITLE',
    'MY_SUB_LIST_EMPTY',
    'MY_SUB_TRAFFIC_LINE',
    'MY_SUB_DEVICES_LINE',
    'MY_SUB_DEVICES_COUNT_SHORT',
    'MY_SUB_UNTIL_LINE',
    'MY_SUB_STATUS_EXPIRED',
    'MY_SUB_STATUS_DISABLED',
    'MY_SUB_STATUS_LIMITED',
    'MY_SUB_DEFAULT_NAME',
    'MY_SUB_SEARCH',
    'MY_SUB_SEARCH_PROMPT',
    'MY_SUB_SEARCH_RESET',
    'MY_SUB_SEARCH_CANCEL',
    'MY_SUB_SEARCH_CANCELLED',
    'MY_SUB_SEARCH_EMPTY_QUERY',
    'MY_SUB_SEARCH_STATE_LOST',
    'MY_SUB_SEARCH_ACTIVE',
    'MY_SUB_SEARCH_NO_RESULTS',
    'MY_SUB_BACK',
    'MY_SUB_BTN_AUTOPAY',
    'MY_SUB_BTN_BACK_TO_LIST',
    'MY_SUB_BTN_BUY',
    'MY_SUB_BTN_BUY_ANOTHER',
    'MY_SUB_BTN_BUY_DEVICES',
    'MY_SUB_BTN_CONNECT_LINK',
    'MY_SUB_BTN_DELETE',
    'MY_SUB_BTN_DISABLE',
    'MY_SUB_BTN_DEVICES',
    'MY_SUB_BTN_ENABLE',
    'MY_SUB_BTN_MANAGE_DEVICES',
    'MY_SUB_BTN_REISSUE',
    'MY_SUB_BTN_RENEW',
    'MY_SUB_BTN_TRAFFIC',
    'MY_SUB_DETAIL_DEVICES',
    'MY_SUB_DETAIL_HEADER',
    'MY_SUB_DETAIL_STATUS',
    'MY_SUB_DETAIL_TRAFFIC',
    'MY_SUB_DETAIL_UNTIL',
    'MY_SUB_DEVICES_MENU',
    'PARTNER_PURCHASE_NOTE_BTN',
    'PARTNER_PURCHASE_NOTE_PROMPT',
    'PARTNER_BRAND_TOGGLE_ON',
    'PARTNER_BRAND_TOGGLE_OFF',
    'SUBSCRIPTION_STATUS_USER_DISABLED',
)


def test_day1_fa_keys_present_and_persian() -> None:
    data = json.loads(FA.read_text(encoding='utf-8'))
    for key in REQUIRED:
        assert key in data, key
        assert data[key].strip()
    assert 'تعرفه' not in data['MAIN_MENU_RICH_TABLE_TARIFF']
    assert 'سرویس' in data['MAIN_MENU_RICH_TABLE_TARIFF']
    assert 'دستگاه' not in data['MAIN_MENU_RICH_DEVICES']
    assert 'کاربر' in data['MAIN_MENU_RICH_DEVICES']
