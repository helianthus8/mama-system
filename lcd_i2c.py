from machine import I2C
from time import sleep, sleep_ms, sleep_us

import const as Const

from typing import List, Optional, Tuple, Union


class LCD:
    def __init__(self,
                 addr: int,
                 cols: int,
                 rows: int,
                 charsize: int = 0x00,
                 i2c: Optional[I2C] = None) -> None:
        self._addr: int = addr
        self._cols: int = cols
        self._rows: int = rows
        self._charsize: int = charsize
        self._backlightval: int = Const.LCD_BACKLIGHT
        if i2c is None:
            self._i2c = I2C(0)
        else:
            self._i2c = i2c

        self._display_control: int = 0
        self._display_mode: int = 0
        self._display_function: int = 0
        self._cursor_position: Tuple[int, int] = (0, 0) 

    @property
    def addr(self) -> int:
        return self._addr

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def charsize(self) -> int:
        return self._charsize

    @property
    def backlightval(self) -> int:
        return self._backlightval

    @property
    def cursor_position(self) -> Tuple[int, int]:
        return self._cursor_position

    @cursor_position.setter
    def cursor_position(self, position: Tuple[int, int]) -> None:
        self.set_cursor(col=position[0], row=position[1]) 

    def begin(self) -> None:
        self._display_function = \
            Const.LCD_4BITMODE | Const.LCD_1LINE | Const.LCD_5x8DOTS

        if self.rows > 1:
            self._display_function |= Const.LCD_2LINE

        if (self.charsize != 0) and (self.rows == 1):
            self._display_function |= Const.LCD_5x10DOTS

        sleep_ms(50)

        self._expander_write(value=self.backlightval)
        sleep(1)

        for _ in range(0, 3):
            self._write_4_bits(value=(0x03 << 4))
            sleep_us(4500) 

        self._write_4_bits(value=(0x02 << 4))

        self._command(value=(Const.LCD_FUNCTIONSET | self._display_function))

        self._display_control = \
            Const.LCD_DISPLAYON | Const.LCD_CURSOROFF | Const.LCD_BLINKOFF
        self.display()

        self.clear()

        self._display_mode = \
            Const.LCD_ENTRYLEFT | Const.LCD_ENTRYSHIFTDECREMENT

        self._command(value=(Const.LCD_ENTRYMODESET | self._display_mode))

        self.home()

    def clear(self) -> None:
        self._command(value=Const.LCD_CLEARDISPLAY)
        sleep_ms(2)   
        self._cursor_position = (0, 0) 

    def home(self) -> None:
        self._command(value=Const.LCD_RETURNHOME)
        sleep_ms(2)    
        self._cursor_position = (0, 0)  

    def no_display(self) -> None:
        self._display_control &= ~Const.LCD_DISPLAYON
        self._command(value=(Const.LCD_DISPLAYCONTROL | self._display_control))

    def display(self) -> None:
        self._display_control |= Const.LCD_DISPLAYON
        self._command(value=(Const.LCD_DISPLAYCONTROL | self._display_control))

    def no_blink(self) -> None:
        self._display_control &= ~Const.LCD_BLINKON
        self._command(value=(Const.LCD_DISPLAYCONTROL | self._display_control))

    def blink(self) -> None:
        self._display_control |= Const.LCD_BLINKON
        self._command(value=(Const.LCD_DISPLAYCONTROL | self._display_control))

    def blink_on(self) -> None:
        self.blink()

    def blink_off(self) -> None:
        self.no_blink()

    def no_cursor(self) -> None:
        self._display_control &= ~Const.LCD_CURSORON
        self._command(value=(Const.LCD_DISPLAYCONTROL | self._display_control))

    def cursor(self) -> None:
        self._display_control |= Const.LCD_CURSORON
        self._command(value=(Const.LCD_DISPLAYCONTROL | self._display_control))

    def cursor_on(self) -> None:
        self.cursor()

    def cursor_off(self) -> None:
        self.no_cursor()

    def set_cursor(self, col: int, row: int) -> None:
        row_offsets: List[int] = [0x00, 0x40, 0x14, 0x54]

        if row > (self.rows - 1):
            row = self.rows - 1

        self._command(
            value=(Const.LCD_SETDDRAMADDR | (col + row_offsets[row]))
        )

        self._cursor_position = (col, row) 

    def scroll_display_left(self) -> None:
        self._command(value=(Const.LCD_CURSORSHIFT | Const.LCD_DISPLAYMOVE | Const.LCD_MOVELEFT))   

    def scroll_display_right(self) -> None:
        self._command(value=(Const.LCD_CURSORSHIFT | Const.LCD_DISPLAYMOVE | Const.LCD_MOVERIGHT)) 

    def left_to_right(self) -> None:
        self._display_mode |= Const.LCD_ENTRYLEFT
        self._command(value=(Const.LCD_ENTRYMODESET | self._display_mode))

    def right_to_left(self) -> None:
        self._display_mode &= ~Const.LCD_ENTRYLEFT
        self._command(value=(Const.LCD_ENTRYMODESET | self._display_mode))

    def no_backlight(self) -> None:
        self._backlightval = Const.LCD_NOBACKLIGHT
        self._expander_write(value=0)

    def backlight(self) -> None:
        self._backlightval = Const.LCD_BACKLIGHT
        self._expander_write(value=0)

    def set_backlight(self, new_val: Union[int, bool]) -> None:
        if new_val:
            self.backlight()        # turn backlight on
        else:
            self.no_backlight()     # turn backlight off

    def get_backlight(self) -> bool:
        return self._backlightval == Const.LCD_BACKLIGHT

    def autoscroll(self) -> None:
        self._display_mode |= Const.LCD_ENTRYSHIFTINCREMENT
        self._command(value=(Const.LCD_ENTRYMODESET | self._display_mode))

    def no_autoscroll(self) -> None:
        self._display_mode &= ~Const.LCD_ENTRYSHIFTINCREMENT
        self._command(value=(Const.LCD_ENTRYMODESET | self._display_mode))

    def create_char(self, location: int, charmap: List[int]) -> None:
        location &= 0x7     # we only have 8, locations 0-7

        self._command(value=(Const.LCD_SETCGRAMADDR | location << 3))
        sleep_us(40)

        for x in range(0, 8):
            self._command(value=charmap[x], mode=Const.RS)
            sleep_us(40)

    def print(self, text: str) -> None:
        _cursor_x, _cursor_y = self.cursor_position

        for char in text:
            self._command(value=ord(char), mode=Const.RS)

        self.cursor_position = (_cursor_x + len(text), _cursor_y)

    def _command(self, value: int, mode: int = 0) -> None:
        high_nib = value & 0xF0
        low_nib = (value << 4) & 0xF0
        self._write_4_bits(value=(high_nib | mode))
        self._write_4_bits(value=(low_nib | mode))

    def _write_4_bits(self, value: int) -> None:
        self._expander_write(value=value)
        self._pulse_enable(value=value)

    def _pulse_enable(self, value: int) -> None:
        self._expander_write(value=(value | Const.EN))
        sleep_us(1)

        self._expander_write(value=(value & ~Const.EN))
        sleep_us(50)

    def _expander_write(self, value: int) -> None:
        self._i2c.writeto(self.addr, bytes([value | self._backlightval]))