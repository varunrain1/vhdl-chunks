--------------------------------------------------------------------------------
-- StreamSource_VC.vhd
-- OSVVM-style source VC for fir_filter.
-- TestCtrl presents tx_valid+tx_data; VC drives one DUT sample (ce=1) per item.
--------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library osvvm;
context osvvm.OsvvmContext;

use work.fir_tb_pkg.all;

entity StreamSource_VC is
  generic (
    MODEL_ID_NAME : string := "StreamSource_VC"
  );
  port (
    clk      : in  std_logic;
    rst      : in  std_logic;
    ce       : out std_logic;
    din      : out data_t;
    tx_valid : in  std_logic;
    tx_data  : in  data_t;
    tx_ready : out std_logic;
    tx_done  : out std_logic
  );
end entity StreamSource_VC;

architecture behavioral of StreamSource_VC is
  constant ID : AlertLogIDType := GetAlertLogID(MODEL_ID_NAME);
begin

  transactor : process
  begin
    ce       <= '0';
    din      <= (others => '0');
    tx_ready <= '0';
    tx_done  <= '0';
    wait until rst = '0';
    log(ID, "Source VC out of reset");

    loop
      tx_ready <= '1';
      wait until rising_edge(clk);
      if tx_valid = '1' then
        -- Drive one active filter cycle
        tx_ready <= '0';
        din      <= tx_data;
        ce       <= '1';
        tx_done  <= '1';
        wait until rising_edge(clk);
        tx_done  <= '0';
        ce       <= '0';
      end if;
    end loop;
  end process transactor;

end architecture behavioral;
