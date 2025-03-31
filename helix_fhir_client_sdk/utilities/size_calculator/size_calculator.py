import locale


class SizeCalculator:
    @staticmethod
    def locale_format_bytes(bytes_size: int, precision: int = 2) -> str:
        """
        Use locale-specific formatting for bytes.

        Args:
            bytes_size: Size in bytes
            precision: Number of decimal places

        Returns:
            Locale-formatted string with unit
        """
        # Set locale to use system default
        locale.setlocale(locale.LC_ALL, "")

        units = [
            (1 << 30, "GB"),  # Gigabytes
            (1 << 20, "MB"),  # Megabytes
            (1 << 10, "KB"),  # Kilobytes
            (1, "bytes"),  # Bytes
        ]

        for factor, unit in units:
            if bytes_size >= factor:
                # Use locale-specific formatting
                return f"{locale.format_string('%.{}f'.format(precision), bytes_size / factor, grouping=True)} {unit}"

        return f"{locale.format_string('%d', bytes_size, grouping=True)} bytes"
