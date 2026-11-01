--------------------------------------------------------------------------------
-- Test_Tone.vhd — architecture of TestCtrl_fir
--------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

library osvvm;
context osvvm.OsvvmContext;

use work.fir_tb_pkg.all;
use work.TestCtrl_fir_utils.all;

architecture Test_Tone of TestCtrl_fir is
  constant ID : AlertLogIDType := GetAlertLogID("Test_Tone");
  shared variable SB : ScoreboardIdType;
begin
  rx_ready <= '1';

  Main : process
    variable sample : data_t;
    variable dl     : delay_line_t := (others => (others => '0'));
    variable y_exp  : acc_t;
    variable n      : integer;
    variable phase  : real;
    variable tone   : real;
    constant AMP    : real := 2000.0;
    constant F_NORM : real := 0.05;  -- cycles per sample
  begin
    test_done <= false;
    tx_valid  <= '0';
    tx_data   <= (others => '0');
    wait until rst = '0';
    wait until rising_edge(clk);
    SB := NewID("SB_Tone", ID);
    log(ID, "=== Test_Tone start ===");

    for n in 0 to 63 loop
      phase  := MATH_2_PI * real(n) * F_NORM;
      tone   := AMP * sin(phase);
      sample := to_signed(integer(tone), C_DATA_WIDTH);
      RefStep(dl, sample, y_exp);
      Push(SB, to_integer(y_exp));
      SendSample(clk, tx_valid, tx_data, tx_ready, tx_done, sample);
    end loop;

    wait for 20 * 10 ns;
    log(ID, "=== Test_Tone done ===");
    test_done <= true;
    wait;
  end process Main;

  Checker : process
  begin
    wait until rst = '0';
    loop
      wait until rising_edge(clk);
      if rx_valid = '1' then
        Check(SB, to_integer(rx_data));
      end if;
    end loop;
  end process Checker;
end architecture Test_Tone;
