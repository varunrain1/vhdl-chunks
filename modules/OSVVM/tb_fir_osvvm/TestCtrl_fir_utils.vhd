--------------------------------------------------------------------------------
-- TestCtrl_fir_utils.vhd
--------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library osvvm;
context osvvm.OsvvmContext;

use work.fir_tb_pkg.all;

package TestCtrl_fir_utils is

  procedure SendSample(
    signal   clk      : in  std_logic;
    signal   tx_valid : out std_logic;
    signal   tx_data  : out data_t;
    signal   tx_ready : in  std_logic;
    signal   tx_done  : in  std_logic;
    constant sample   : in  data_t
  );

  -- Bit-true expected output + update delay line (mirrors transversal RTL)
  procedure RefStep(
    variable dl     : inout delay_line_t;
    constant sample : in    data_t;
    variable y_exp  : out   acc_t
  );

end package TestCtrl_fir_utils;

package body TestCtrl_fir_utils is

  procedure SendSample(
    signal   clk      : in  std_logic;
    signal   tx_valid : out std_logic;
    signal   tx_data  : out data_t;
    signal   tx_ready : in  std_logic;
    signal   tx_done  : in  std_logic;
    constant sample   : in  data_t
  ) is
  begin
    wait until rising_edge(clk) and tx_ready = '1';
    tx_data  <= sample;
    tx_valid <= '1';
    wait until rising_edge(clk) and tx_done = '1';
    tx_valid <= '0';
  end procedure;

  procedure RefStep(
    variable dl     : inout delay_line_t;
    constant sample : in    data_t;
    variable y_exp  : out   acc_t
  ) is
    variable y : acc_t;
    variable i : integer;
  begin
    y := (others => '0');
    for i in 0 to C_TAPS-1 loop
      y := y + resize(dl(i) * C_COEFFS(i), C_ACC_WIDTH);
    end loop;
    y_exp := y;
    for i in C_TAPS-1 downto 1 loop
      dl(i) := dl(i-1);
    end loop;
    dl(0) := sample;
  end procedure;

end package body TestCtrl_fir_utils;
