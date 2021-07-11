import binascii
import mmap
import struct
import sys


class TunedLibExtract:
    def __init__(self):
        self.IsSnap845Family = False
        self.TunedName = ""
        self.TunedLib = ""
        self.DataOffset = 0

    def FloatToHex(self, f):
        return hex(struct.unpack("<I", struct.pack("<f", f))[0])

    def OpenTunedLib(self, name):
        if "tuned" not in name:
            raise NameError("Expected com.qti.tuned*.bin")
        self.TunedName = name
        try:
            with open(self.TunedName, "rb") as f:
                self.TunedLib = mmap.mmap(
                    f.fileno(), 0, access=mmap.ACCESS_READ
                )
                # на старых 1.1.х версиях выравнивание было по 4 байта
                index = self.TunedLib.find("1.1.".encode(), 0)
                # ???????????????????????? неведомая ебанина от 378
                index2 = self.TunedLib.find(
                    "ParameterFileConverter V.7.0.4.39070".encode(), 0
                )
                if index != -1 or index2 != -1:
                    self.IsSnap845Family = True
                    # на 845 оффсет даты лежит через B0 (176) от начала файла
                    self.TunedLib.seek(176, 0)
                    self.DataOffset = int.from_bytes(
                        self.TunedLib.read(4), "little"
                    )
                else:
                    # на нормальных снапах оффсет даты всегда будет через C0 (192) от начала файла
                    self.TunedLib.seek(192, 0)
                    self.DataOffset = int.from_bytes(
                        self.TunedLib.read(4), "little"
                    )
        except Exception as e:
            print(e)
            exit()

    def GetOffsetsAndLengthsByName(self, name):
        offsets = []
        lengths = []
        index = self.TunedLib.find(name.encode(), 0)
        while index >= 0:
            index = (
                index + 48 if not self.IsSnap845Family else index + 52
            )  # оффсет будет через 30 (48) после названия для нормальных либ или через 34 (52) для хуйни типа 845
            self.TunedLib.seek(index, 0)
            offsets.append(
                int.from_bytes(self.TunedLib.read(4), "little")
            )  # перевод 4 байтов длины в инт
            index = (
                index + 8 if not self.IsSnap845Family else index + 4
            )  # длина будет через 4 байта после оффсета для нормальных либ или сразу за оффсетом для 845
            self.TunedLib.seek(index, 0)
            length = self.TunedLib.read(2).hex()  # длина всего 2 байта
            length = (
                length[2:4] + length[0:2]
            )  # переворот длины в хексе с предподвыподвертом
            lengths.append(int(length, 16))  # перевод в инт из хекса
            index = self.TunedLib.find(
                name.encode(), index
            )  # дальше пусть ищет по циклу
        return list(zip(offsets, lengths))

    def ExtractDataByOffsets(self, offsets):
        hexdata = []
        for offset in offsets:
            self.TunedLib.seek(
                self.DataOffset, 0
            )  # перехожу на начало блока дата
            self.TunedLib.seek(offset[0], 1)
            hexdata.append(self.TunedLib.read(offset[1]).hex())
        return hexdata

    def DecodeAwb(self, hexdata):
        n = 8  # 8 символов = 4 байта
        hexdata = [
            hexdata[0][i : i + n] for i in range(0, len(hexdata[0]), n)
        ]  # деление всей строки на список значений по 4 байта
        filter_hex = ["01000000", "02000000", "00000000"]  # фильтр мусора
        hexdata = [
            i for i in hexdata if not any([e for e in filter_hex if e in i])
        ]  # удаление мусора по фильтру
        awb_float = [
            struct.unpack("<f", binascii.unhexlify(value)) for value in hexdata
        ]  # перевод из хекса во флоат
        awb_float = [
            "%.6f" % elem for elem in awb_float
        ]  # оставляю 5 знаков после запятой
        awb_float = list(zip(awb_float[0::2], awb_float[1::2]))  # хз надо ли
        return awb_float

    def DecodeCct(self, hexdata):
        cct_float = []
        if hexdata == []:
            return
        n = 8  # 8 символов = 4 байта
        for cct_hex in hexdata:
            cct_hex = [
                cct_hex[i : i + n] for i in range(0, len(cct_hex), n)
            ]  # деление всей строки на список значений по 4 байта
            filter_hex = ["01000000", "02000000", "00000000"]  # фильтр мусора
            cct_hex = [
                i
                for i in cct_hex
                if not any([e for e in filter_hex if e in i])
            ]
            cct_hex = [
                struct.unpack("<f", binascii.unhexlify(value))
                for value in cct_hex
            ]
            cct_hex = ["%.5f" % elem for elem in cct_hex]
            cct_start = cct_hex[
                0::11
            ]  # короче в строке нулевое значение и каждое одиннадцатое это начало ренжа температуры
            cct_end = cct_hex[
                1::11
            ]  # точно так же первое значение и через каждые 11 значений это конец ренжа температуры
            cct_values = [x for x in cct_hex if x not in cct_start]
            cct_values = [
                x for x in cct_values if x not in cct_end
            ]  # убираю ренж температур потому что не нужны
            cct_values = list(filter(None, cct_values))  # пустые значения
            cct_values = [x for x in cct_values if x]  # пустые значения
            if (
                len(cct_values) % 9 == 0 and cct_values != []
            ):  # еще раз пустые значения потому что пиздец
                cct_float += zip(
                    *[iter(cct_values)] * 9
                )  # каждые 9 значений это одна матрица
        return cct_float


if __name__ == "__main__":
    tuned_name = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "com.qti.tuned.j20c_ofilm_imx682_wide_global.bin"
    )

    libextract = TunedLibExtract()
    libextract.OpenTunedLib(tuned_name)
    print(f"{libextract.DataOffset!a}")

    cc13_offsets = libextract.GetOffsetsAndLengthsByName("mod_cc13_cct_data")
    cc12_offsets = libextract.GetOffsetsAndLengthsByName("mod_cc12_cct_data")
    refptv1_offset = libextract.GetOffsetsAndLengthsByName("refPtV1")
    hexcc13 = libextract.ExtractDataByOffsets(cc13_offsets)
    hexcc12 = libextract.ExtractDataByOffsets(cc12_offsets)
    hexawb = libextract.ExtractDataByOffsets(refptv1_offset)
    awb = libextract.DecodeAwb(hexawb)
    print(refptv1_offset[0][0])
    print(hexawb)
    print(awb)

    cct = []
    cct13 = libextract.DecodeCct(hexcc13)
    cct12 = libextract.DecodeCct(hexcc12)
    cct = cct + cct13 if cct13 is not None else cct
    cct = cct + cct12 if cct12 is not None else cct
    cct = list(dict.fromkeys(cct))  # убирает дубликаты
    for matrix in cct:
        print(matrix)
