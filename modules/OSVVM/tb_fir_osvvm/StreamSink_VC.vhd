--------------------------------------------------------------------------------
-- StreamSink_VC.vhd
-- Samples fir_filter dout on each active ce cycle and presents it to TestCtrl.
--------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library osvvm;
context osvvm.OsvvmContext;

use work.fir_tb_pkg.all;

entity StreamSink_VC is
  generic (
    MODEL_ID_NAME : string := "StreamSink_VC"
  );
  port (
    clk      : in  std_logic;
    rst      : in  std_logic;
    ce_in    : in  std_logic;
    dout     : in  acc_t;
    rx_valid : out std_logic;
    rx_data  : out acc_t;
    rx_ready : in  std_logic
  );
end entity StreamSink_VC;

architecture behavioral of StreamSink_VC is
  constant ID : AlertLogIDType := GetAlertLogID(MODEL_ID_NAME);
begin

  monitor : process
  begin
    rx_valid <= '0';
    rx_data  <= (others => '0');
    wait until rst = '0';
    log(ID, "Sink VC out of reset");

    loop
      wait until rising_edge(clk);
      rx_valid <= '0';
      if ce_in = '1' then
        -- DUT updates registered dout on this edge; sample after a delta
        wait for 0 ns;
        rx_data  <= dout;
        rx_valid <= '1';
        -- Hold one cycle so Checker / TestCtrl can see rx_valid
      end if;
    end loop;
  end process monitor;

end architecture behavioral;
