from typing import Literal

Language = Literal["ko", "en"]

MESSAGES: dict[str, dict[Language, str]] = {
    "app_tagline": {
        "ko": "당신을 위한 When2meet 초안 자동완성",
        "en": "A first-draft availability for When2meet",
    },
    "sign_in_google": {"ko": "Google로 계속하기", "en": "Continue with Google"},
    "sign_in_dev": {"ko": "개발용 로그인", "en": "Development sign-in"},
    "signed_in_as": {"ko": "로그인됨", "en": "Signed in"},
    "sign_out": {"ko": "로그아웃", "en": "Sign out"},
    "oauth_unavailable": {
        "ko": "Google 로그인은 아직 설정되지 않았습니다.",
        "en": "Google sign-in is not configured yet.",
    },
}


def translate(key: str, language: Language) -> str:
    return MESSAGES[key][language]
