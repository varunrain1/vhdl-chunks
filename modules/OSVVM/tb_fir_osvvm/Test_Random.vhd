--------------------------------------------------------------------------------
-- Test_Random.vhd — architecture of TestCtrl_fir
--------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library osvvm;
context osvvm.OsvvmContext;

use work.fir_tb_pkg.all;
use work.TestCtrl_fir_utils.all;

architecture Test_Random of TestCtrl_fir is
  constant ID : AlertLogIDType := GetAlertLogID("Test_Random");
  shared variable SB  : ScoreboardIdType;
  shared variable RV  : RandomPType;
  shared variable Cov : CoverageIdType;
begin
  rx_ready <= '1';

  Main : process
    variable sample : data_t;
    variable dl     : delay_line_t := (others => (others => '0'));
    variable y_exp  : acc_t;
    variable n      : integer;
    variable mag    : integer;
  begin
    test_done <= false;
    tx_valid  <= '0';
    tx_data   <= (others => '0');
    wait until rst = '0';
    wait until rising_edge(clk);

    RV.InitSeed(RV'instance_name);
    SB  := NewID("SB_Random", ID);
    Cov := NewID("COV_Random", ID);
    AddBins(Cov, GenBin(0, 3));

    log(ID, "=== Test_Random start (200 samples) ===");

    for n in 0 to 199 loop
      sample := to_signed(
        RV.RandInt(-(2**(C_DATA_WIDTH-3)), 2**(C_DATA_WIDTH-3)-1),
        C_DATA_WIDTH);
      mag := abs(to_integer(sample));
      if mag < 10 then
        ICover(Cov, 0);
      elsif mag < 500 then
        ICover(Cov, 1);
      elsif mag < 2000 then
        ICover(Cov, 2);
      else
        ICover(Cov, 3);
      end if;

      RefStep(dl, sample, y_exp);
      Push(SB, to_integer(y_exp));
      SendSample(clk, tx_valid, tx_data, tx_ready, tx_done, sample);
    end loop;

    wait for 20 * 10 ns;
    AffirmIf(ID, IsCovered(Cov), "Coverage incomplete in Test_Random");
    WriteBin(Cov);
    log(ID, "=== Test_Random done ===");
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
end architecture Test_Random;
