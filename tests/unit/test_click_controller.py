
from holocontrol.application.services.controllador_click import ClickController


def test_click_only_once_while_gesture_is_held():
    controller = ClickController()

    assert controller.should_click(True) is True
    assert controller.should_click(True) is False
    assert controller.should_click(True) is False


def test_new_gesture_allows_another_click():
    controller = ClickController()

    assert controller.should_click(True) is True
    assert controller.should_click(False) is False
    assert controller.should_click(True) is True


def test_reset_allows_a_new_click():
    controller = ClickController()

    assert controller.should_click(True) is True

    controller.reset()

    assert controller.should_click(True) is True
