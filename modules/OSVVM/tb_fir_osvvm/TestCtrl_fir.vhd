--------------------------------------------------------------------------------
-- TestCtrl_fir.vhd
-- Entity declaration only. Each scenario is a separate architecture file:
--   Test_Impulse.vhd, Test_Step.vhd, Test_Tone.vhd, Test_Random.vhd
-- Bind with the configurations in tb_fir_configs.vhd
--------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library osvvm;
context osvvm.OsvvmContext;

use work.fir_tb_pkg.all;

entity TestCtrl_fir is
  port (
    clk       : in  std_logic;
    rst       : in  std_logic;
    tx_valid  : out std_logic;
    tx_data   : out data_t;
    tx_ready  : in  std_logic;
    tx_done   : in  std_logic;
    rx_valid  : in  std_logic;
    rx_data   : in  acc_t;
    rx_ready  : out std_logic;
    test_done : out boolean
  );
end entity TestCtrl_fir;
