
from holocontrol.application.services.controlador_click import ClickController


def test_click_only_once_while_gesture_is_held():
    controller = ClickController()

    assert controller.deberia_click(True) is True
    assert controller.deberia_click(True) is False
    assert controller.deberia_click(True) is False


def test_new_gesture_allows_another_click():
    controller = ClickController()

    assert controller.deberia_click(True) is True
    assert controller.deberia_click(False) is False
    assert controller.deberia_click(True) is True


def test_reset_allows_a_new_click():
    controller = ClickController()

    assert controller.deberia_click(True) is True

    controller.resetear()

    assert controller.deberia_click(True) is True
