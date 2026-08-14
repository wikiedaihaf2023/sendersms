import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.repositories import ProviderSettingsRepository


def test_provider_settings_round_trip():
    repo = ProviderSettingsRepository()
    repo.save_provider_settings(
        username='demo-user',
        provider='sapa_phone',
        yemen_mobile_url='https://yemen.test',
        sapa_phone_url='https://sapa.test',
        sapa_phone_username='user1',
        sapa_phone_password='pass1',
        sapa_phone_sender='MSG',
        sapa_phone_api_key='k1',
    )

    saved = repo.get_provider_settings('demo-user')
    assert saved['provider'] == 'sapa_phone'
    assert saved['sapa_phone_url'] == 'https://sapa.test'
    assert saved['sapa_phone_username'] == 'user1'
