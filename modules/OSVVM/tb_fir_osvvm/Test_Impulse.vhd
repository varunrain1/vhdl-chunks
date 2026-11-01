--------------------------------------------------------------------------------
-- Test_Impulse.vhd — architecture of TestCtrl_fir
--------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library osvvm;
context osvvm.OsvvmContext;

use work.fir_tb_pkg.all;
use work.TestCtrl_fir_utils.all;

architecture Test_Impulse of TestCtrl_fir is
  constant ID : AlertLogIDType := GetAlertLogID("Test_Impulse");
  shared variable SB : ScoreboardIdType;
begin
  rx_ready <= '1';

  Main : process
    variable sample : data_t;
    variable dl     : delay_line_t := (others => (others => '0'));
    variable y_exp  : acc_t;
    variable n      : integer;
  begin
    test_done <= false;
    tx_valid  <= '0';
    tx_data   <= (others => '0');
    wait until rst = '0';
    wait until rising_edge(clk);
    SB := NewID("SB_Impulse", ID);
    log(ID, "=== Test_Impulse start ===");

    for n in 0 to 3 loop
      sample := (others => '0');
      RefStep(dl, sample, y_exp);
      Push(SB, to_integer(y_exp));
      SendSample(clk, tx_valid, tx_data, tx_ready, tx_done, sample);
    end loop;

    sample := to_signed(1024, C_DATA_WIDTH);
    RefStep(dl, sample, y_exp);
    Push(SB, to_integer(y_exp));
    SendSample(clk, tx_valid, tx_data, tx_ready, tx_done, sample);

    for n in 0 to C_TAPS + 2 loop
      sample := (others => '0');
      RefStep(dl, sample, y_exp);
      Push(SB, to_integer(y_exp));
      SendSample(clk, tx_valid, tx_data, tx_ready, tx_done, sample);
    end loop;

    wait for 20 * 10 ns;
    log(ID, "=== Test_Impulse done ===");
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
end architecture Test_Impulse;
