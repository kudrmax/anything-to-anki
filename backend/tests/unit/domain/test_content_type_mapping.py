from backend.domain.value_objects.content_type import ContentType, resolve_content_type
from backend.domain.value_objects.input_method import InputMethod


class TestResolveContentType:
    def test_text_pasted_maps_to_text(self) -> None:
        assert resolve_content_type(InputMethod.TEXT_PASTED) == ContentType.TEXT

    def test_lyrics_pasted_maps_to_lyrics(self) -> None:
        assert resolve_content_type(InputMethod.LYRICS_PASTED) == ContentType.LYRICS

    def test_subtitles_file_maps_to_text(self) -> None:
        assert resolve_content_type(InputMethod.SUBTITLES_FILE) == ContentType.TEXT

    def test_video_file_maps_to_video(self) -> None:
        assert resolve_content_type(InputMethod.VIDEO_FILE) == ContentType.VIDEO

    def test_youtube_url_maps_to_video(self) -> None:
        assert resolve_content_type(InputMethod.YOUTUBE_URL) == ContentType.VIDEO

    def test_all_input_methods_covered(self) -> None:
        for method in InputMethod:
            resolve_content_type(method)
