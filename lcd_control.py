from RPLCD.i2c import CharLCD

LCD_I2C_ADDRESS = 0x27
LCD_PORT = 1

lcd = CharLCD(i2c_expander='PCF8574', address=LCD_I2C_ADDRESS, port=LCD_>
              cols=16, rows=2, charmap='A02', auto_linebreaks=True)


def show_message(line1: str, line2: str = ""):
    lcd.clear()
    lcd.write_string(line1[:16])
    if line2:
        lcd.crlf()
        lcd.write_string(line2[:16])


def clear():
    lcd.clear()