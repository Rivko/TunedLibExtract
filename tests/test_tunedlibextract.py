from tunedlibextract import __version__
from tunedlibextract.TunedLibExtract import TunedLibExtract


def test_version():
    assert __version__ == "0.1.0"


def test_getting_data_offset():
    testlibextract = TunedLibExtract()
    testlibextract.OpenTunedLib(
        "com.qti.tuned.j20c_ofilm_imx682_wide_global.bin"
    )
    assert str(testlibextract.DataOffset) == "354760", "Data offset is wrong"


def test_float_to_hex():
    testlibextract = TunedLibExtract()
    assert testlibextract.FloatToHex(0.707706) == "0x3f352c38"


def test_getting_refptv1_offset():
    testlibextract = TunedLibExtract()
    testlibextract.OpenTunedLib(
        "com.qti.tuned.j20c_ofilm_imx682_wide_global.bin"
    )
    refptv1_offset = testlibextract.GetOffsetsAndLengthsByName("refPtV1")
    assert str(refptv1_offset[0][0]) == "12394632", "Refptv1 offset is wrong"
