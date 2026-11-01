"""Every NVIDIA GPU and driver gets the newest GPU build it can run (vt/gpu_detect.py)."""
import pytest

from vt.gpu_detect import Gpu, _cc_from_name, choose


@pytest.mark.parametrize("gpus,flavour", [
    ([Gpu("NVIDIA GeForce RTX 5090", 12.0, (575, 51))], "cu128"),          # Blackwell runs only on CUDA 12.8
    ([Gpu("NVIDIA GeForce RTX 5070", 12.0, (560, 0))], "cpu"),             # ... and needs driver 570
    ([Gpu("NVIDIA GeForce RTX 4050 Laptop GPU", 8.9, (617, 42))], "cu124"),
    ([Gpu("Tesla V100-PCIE-16GB", 7.0, (580, 0)), Gpu("NVIDIA GeForce RTX 3060", 8.6, (580, 0))], "cu124"),   # the owner's GPU server
    ([Gpu("NVIDIA GeForce GTX 1060", 6.1, (512, 0))], "cu118"),            # driver older than 525
    ([Gpu("NVIDIA GeForce GTX 970", 5.2, (531, 0))], "cu124"),             # Maxwell still on the default
    ([Gpu("Tesla K80", 3.7, (470, 0))], "cu118"),
    ([Gpu("NVIDIA GeForce GTX 760", 3.0, (470, 0))], "cpu"),               # Kepler 3.0: no build supports it
    ([Gpu("NVIDIA GeForce GTX 1080", 6.1, (390, 0))], "cpu"),              # a driver too old for anything
    ([], "cpu"),
])
def test_the_newest_build_each_machine_can_run(gpus, flavour):
    assert choose(gpus, "win32").flavour == flavour


def test_mixed_cards_take_what_all_of_them_run_and_the_reasons_are_plain():
    d = choose([Gpu("NVIDIA GeForce RTX 5090", 12.0, (575, 0)), Gpu("NVIDIA GeForce GTX 1080", 6.1, (575, 0))], "linux")
    assert d.flavour == "cpu" and "different builds" in d.why
    old = choose([Gpu("NVIDIA GeForce GTX 1060", 6.1, (512, 0))], "linux")
    assert not old.asr_on_gpu and "driver" in old.why
    assert choose([Gpu("Apple", 8.0, (600, 0))], "darwin").flavour == "cpu"


def test_names_identify_cards_when_the_driver_does_not_say():
    assert _cc_from_name("NVIDIA GeForce RTX 5080") == 12.0
    assert _cc_from_name("Tesla T4") == 7.5 and _cc_from_name("NVIDIA GeForce GTX 1660 SUPER") == 7.5
    assert _cc_from_name("Some Unknown Card") is None
