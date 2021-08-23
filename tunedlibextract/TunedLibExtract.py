import binascii
import mmap
import os
import struct
import sys
import urllib.request

__version__ = "0.5.0"


class TunedLibExtract:
    def __init__(self):
        self.offset_to_data = 0
        self.offset_to_offset = 0
        self.offset_to_length = 0
        self.tuned_name = ""
        self.tuned_lib = ""
        self.data_offset = 0

    def float_to_hex(self, f):
        return hex(struct.unpack("<I", struct.pack("<f", f))[0])

    def matrix_to_hex(self, matrix):
        converted = []
        for value in list(matrix):
            converted.append(self.float_to_hex(float(value)))
        return converted

    def check_if_in_range(self, value):
        if 0.0 <= value <= 20000.0 and round(value, 2) == value:
            return True
        return False

    def open_tuned_lib(self, name):
        if "tuned" not in name:
            print("Expected com.qti.tuned*.bin")
            os.system("pause")
            sys.exit()
        self.tuned_name = name
        try:
            with open(self.tuned_name, "rb") as f:
                self.tuned_lib = mmap.mmap(
                    f.fileno(), 0, access=mmap.ACCESS_READ
                )
                snap845 = [
                    "ParameterParser V1.1.".encode(),
                    "ParameterFileConverter V.7.0.4.39070".encode(),
                ]
                # на снапе845 на старых 1.1.х версиях выравнивание было по 4 байта
                snap888 = [
                    "Parameter Parser V3.0.".encode()
                ]  # снап888 от ванплас9про
                self.offset_to_data = (
                    192  # на остальных должен лежать через C0 (192)
                )
                self.offset_to_offset = (
                    48  # длина от названия параметра до его оффсета
                )
                self.offset_to_length = 8  # длина от оффсета до его размера
                for i in range(0, len(snap845)):
                    if self.tuned_lib.find(snap845[i]) != -1:
                        self.offset_to_data = 176  # на 845 оффсет даты лежит через B0 (176) от начала файла
                        self.offset_to_offset = 52
                        self.offset_to_length = 4
                for i in range(0, len(snap888)):
                    if self.tuned_lib.find(snap888[i], 0) != -1:
                        self.offset_to_data = 184  # на 888 оффсет даты лежит через B8 (184) от начала файла
                        self.offset_to_offset = 44
                        self.offset_to_length = 4

                self.tuned_lib.seek(self.offset_to_data, 0)
                self.data_offset = int.from_bytes(
                    self.tuned_lib.read(4), "little"
                )
        except Exception as e:
            print(e)
            os.system("pause")

    def get_offsets_and_lengths_by_name(self, name):
        offsets = []
        lengths = []
        index = self.tuned_lib.find(name.encode(), 0)
        while index >= 0:
            index = (
                index + self.offset_to_offset
            )  # оффсет будет через 30 (48) после названия для нормальных либ или через 34 (52) для хуйни типа 845
            self.tuned_lib.seek(index, 0)
            offsets.append(
                int.from_bytes(self.tuned_lib.read(4), "little")
            )  # перевод 4 байтов длины в инт
            index = (
                index + self.offset_to_length
            )  # длина будет через 4 байта после оффсета для нормальных либ или сразу за оффсетом для 845
            self.tuned_lib.seek(index, 0)
            length = self.tuned_lib.read(2).hex()  # длина всего 2 байта
            length = (
                length[2:4] + length[0:2]
            )  # переворот длины в хексе с предподвыподвертом
            lengths.append(int(length, 16))  # перевод в инт из хекса
            index = self.tuned_lib.find(
                name.encode(), index
            )  # дальше пусть ищет по циклу
        return list(zip(offsets, lengths))

    def extract_data_by_offsets(self, offsets):
        hexdata = []
        for offset in offsets:
            self.tuned_lib.seek(
                self.data_offset, 0
            )  # перехожу на начало блока дата
            self.tuned_lib.seek(offset[0], 1)
            hexdata.append(self.tuned_lib.read(offset[1]).hex())
        return hexdata

    def decode_awb(self, hexdata):
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

    def decode_cct(self, hexdata):
        cct_matrix = []
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
            # cct_start = cct_hex[
            #     0::11
            # ]  # короче в строке нулевое значение и каждое одиннадцатое это начало ренжа температуры
            # cct_end = cct_hex[
            #     1::11
            # ]  # точно так же первое значение и через каждые 11 значений это конец ренжа температуры
            # cct_values = [x for x in cct_hex if x not in cct_start]
            # cct_values = [
            #     x for x in cct_values if x not in cct_end
            # ]  # убираю ренж температур потому что не нужны
            cct_values = cct_hex
            cct_values = list(filter(None, cct_values))  # пустые значения
            cct_values = [x for x in cct_values if x]  # пустые значения
            if (
                len(cct_values) % 11 == 0 and cct_values != []
            ):  # еще раз пустые значения потому что пиздец
                cct_matrix += zip(
                    *[iter(cct_values)] * 11
                )  # каждые 11 значений это одна матрица
        return cct_matrix

    def decode_aec(self, hexdata):
        n = 8  # данные об одном ренже люксов занимают примерно 30 (48)
        for aec_hex in hexdata:
            aec_hex = [
                aec_hex[i : i + n] for i in range(0, len(aec_hex), n)
            ]  # деление всей строки на список значений
            filter_hex = ["01000000", "02000000", "00000000"]  # фильтр мусора
            aec_hex = [
                i
                for i in aec_hex
                if not any([e for e in filter_hex if e in i])
            ]
            aec_hex = [
                struct.unpack("<f", binascii.unhexlify(value))
                for value in aec_hex
            ]
            aec_hex = [i[0] for i in aec_hex if self.check_if_in_range(i[0])]
            # print(aec_hex)


if __name__ == "__main__":
    tuned_name = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "com.qti.tuned.j20c_ofilm_imx682_wide_global.bin"
    )

    libextract = TunedLibExtract()
    libextract.open_tuned_lib(tuned_name)

    cc13_offsets = libextract.get_offsets_and_lengths_by_name(
        "mod_cc13_cct_data"
    )
    cc13_aec = libextract.get_offsets_and_lengths_by_name("mod_cc13_aec_data")
    aec13_cc = [int(aec[0]) + int(aec[1]) for aec in cc13_aec]
    # cc13_offsets = [offset for offset in cc13_offsets if offset[0] in aec13_cc]

    cc12_offsets = libextract.get_offsets_and_lengths_by_name(
        "mod_cc12_cct_data"
    )
    cc12_aec = libextract.get_offsets_and_lengths_by_name("mod_cc12_aec_data")
    aec12_cc = [int(aec[0]) + int(aec[1]) for aec in cc12_aec]
    # cc12_offsets = [offset for offset in cc12_offsets if offset[0] in aec12_cc]
    refptv1_offset = libextract.get_offsets_and_lengths_by_name("refPtV1")

    hexcc13 = libextract.extract_data_by_offsets(cc13_offsets)
    hexcc12 = libextract.extract_data_by_offsets(cc12_offsets)
    hexcc12aec = libextract.extract_data_by_offsets(cc12_aec)
    hexcc13aec = libextract.extract_data_by_offsets(cc13_aec)
    hexawb = libextract.extract_data_by_offsets(refptv1_offset)

    cc13aec = libextract.decode_aec(hexcc13aec)
    cc12aec = libextract.decode_aec(hexcc12aec)
    awb = libextract.decode_awb(hexawb)
    awb_order = [
        "StatsIlluminantHigh",
        "StatsIlluminantD75",
        "StatsIlluminantD65",
        "StatsIlluminantD50",
        "StatsIlluminantCW",
        "StatsIlluminantFluorescent",
        "StatsIlluminantTL84",
        "StatsIlluminantIncandescent",
        "StatsIlluminantHorizon",
        "StatsIlluminantLow",
    ]
    print("\nOrder in libs:                      RG            BG")
    for id, pair in enumerate(awb_order):
        print(f"{pair:30}: {awb[id]}")

    gcam_order = [2, 1, 7, 6, 4, 8, 3, 5]
    print("\nOrder for gcam:                     RG            BG")
    for pair in gcam_order:
        print(f"{awb_order[pair]:30}: {awb[pair]}")

    print("\nAWB in Java:")
    print(
        f"WB_BG = new float[]{{{awb[2][1]}f, {awb[1][1]}f, {awb[7][1]}f, {awb[6][1]}f, {awb[4][1]}f, {awb[8][1]}f, {awb[3][1]}f, {awb[5][1]}f}};"
    )
    print(
        f"WB_RG = new float[]{{{awb[2][0]}f, {awb[1][0]}f, {awb[7][0]}f, {awb[6][0]}f, {awb[4][0]}f, {awb[8][0]}f, {awb[3][0]}f, {awb[5][0]}f}};"
    )

    print("\nAWB in HEX:\nRG")
    for pair in gcam_order:
        print(str(libextract.float_to_hex(float(awb[pair][0]))))

    print("\nBG")
    for pair in gcam_order:
        print(str(libextract.float_to_hex(float(awb[pair][1]))))

    cct = []
    cct13 = libextract.decode_cct(hexcc13)
    cct12 = libextract.decode_cct(hexcc12)
    # ебаные пустые авб от сяомы
    cct = cct + cct13 if cct13 is not None else cct
    cct = cct + cct12 if cct12 is not None else cct
    # убирает дубликаты
    cct = list(dict.fromkeys(cct))
    print("\nCCT:")
    for matrix in cct:
        print(
            f"Temperature trigger: {int(float(matrix[0]))} - {int(float(matrix[1]))}"
        )  # это просто пиздец прости меня господи
        matrix = matrix[2:]
        print(matrix)
        matrix_in_hex = libextract.matrix_to_hex(matrix)
        print("In HEX:")
        for hex_value in matrix_in_hex:
            print(hex_value)
        print("\n")

    with open(libextract.tuned_name + ".txt", "w", encoding="utf-8") as f:
        f.write("Order in libs:                      RG            BG\n")
        for id, pair in enumerate(awb_order):
            f.write(f"{pair:30}: {awb[id]}\n")
        f.write("\nOrder for gcam:                     RG            BG\n")
        for pair in gcam_order:
            f.write(f"{awb_order[pair]:30}: {awb[pair]}\n")
        f.write("\nAWB in HEX:\nRG\n")
        for pair in gcam_order:
            f.write(str(libextract.float_to_hex(float(awb[pair][0]))) + "\n")
        f.write("\nBG\n")
        for pair in gcam_order:
            f.write(str(libextract.float_to_hex(float(awb[pair][1]))) + "\n")
        f.write("\nAWB in Java:\n")
        f.write(
            f"WB_BG = new float[]{{{awb[2][1]}f, {awb[1][1]}f, {awb[7][1]}f, {awb[6][1]}f, {awb[4][1]}f, {awb[8][1]}f, {awb[3][1]}f, {awb[5][1]}f}};\n"
        )
        f.write(
            f"WB_RG = new float[]{{{awb[2][0]}f, {awb[1][0]}f, {awb[7][0]}f, {awb[6][0]}f, {awb[4][0]}f, {awb[8][0]}f, {awb[3][0]}f, {awb[5][0]}f}};\n"
        )

        f.write("\nCCT:\n")
        for matrix in cct:
            f.write(
                f"Temperature trigger: {int(float(matrix[0]))} - {int(float(matrix[1]))}\n"
            )
            matrix = matrix[2:]
            f.write(str(matrix) + "\n")
            matrix_in_hex = libextract.matrix_to_hex(matrix)
            f.write("In HEX:\n")
            for hex_value in matrix_in_hex:
                f.write(hex_value + "\n")
            f.write("\n")
    try:
        git_version = urllib.request.urlopen(
            "https://raw.githubusercontent.com/Rivko/TunedLibExtract/main/VERSION"
        )
        git_version = str(git_version.read().strip().decode("utf-8"))
        if git_version != __version__:
            print(
                "New version is available @ https://github.com/Rivko/TunedLibExtract/releases"
            )
    except urllib.error.HTTPError as e:
        print(e)
    os.system("pause")
