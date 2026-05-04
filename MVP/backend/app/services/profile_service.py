from app.repositories.profile_repository import ProfileRepository


def get_profile_summary() -> dict[str, object]:
    repo = ProfileRepository()
    return repo.get_profile_summary()
