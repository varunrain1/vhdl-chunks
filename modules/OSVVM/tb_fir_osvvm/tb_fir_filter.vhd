--------------------------------------------------------------------------------
-- tb_fir_filter.vhd
-- OSVVM harness for fir_filter:
--   DUT + StreamSource_VC + StreamSink_VC + scoreboard + coverage + TestCtrl
--------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

library osvvm;
context osvvm.OsvvmContext;

use work.fir_tb_pkg.all;

entity tb_fir_filter is
end entity tb_fir_filter;

architecture test_harness of tb_fir_filter is

  constant tCLK : time := 10 ns;

  signal clk      : std_logic := '0';
  signal rst      : std_logic := '1';
  signal ce       : std_logic := '0';
  signal din      : data_t := (others => '0');
  signal dout     : acc_t := (others => '0');

  -- Source VC transaction interface
  signal tx_valid : std_logic := '0';
  signal tx_data  : data_t := (others => '0');
  signal tx_ready : std_logic;
  signal tx_done  : std_logic;

  -- Sink VC observe interface
  signal rx_valid : std_logic;
  signal rx_data  : acc_t;
  signal rx_ready : std_logic := '1';

  signal test_done : boolean := false;

  -- OSVVM IDs / scoreboard / coverage (harness-owned)
  signal sb_push  : acc_t := (others => '0');
  signal sb_push_v: std_logic := '0';

begin

  ------------------------------------------------------------
  -- Clock / reset
  ------------------------------------------------------------
  CreateClock(clk, tCLK);

  ResetProc : process
  begin
    SetAlertLogName("TB_FIR_FILTER");
    TranscriptOpen("./tb_fir_filter_transcript.txt");
    SetTranscriptMirror(true);

    rst <= '1';
    wait for 5 * tCLK;
    wait until rising_edge(clk);
    rst <= '0';
    log("TB", "Reset deasserted");
    wait;
  end process ResetProc;

  ------------------------------------------------------------
  -- DUT
  ------------------------------------------------------------
  u_dut : entity work.fir_filter
    generic map (
      DATA_WIDTH  => C_DATA_WIDTH,
      COEFF_WIDTH => C_COEFF_WIDTH,
      TAPS        => C_TAPS,
      ACC_WIDTH   => C_ACC_WIDTH
    )
    port map (
      clk  => clk,
      rst  => rst,
      ce   => ce,
      din  => din,
      dout => dout
    );

  ------------------------------------------------------------
  -- Source VC
  ------------------------------------------------------------
  u_src : entity work.StreamSource_VC
    generic map (MODEL_ID_NAME => "FIR_SRC")
    port map (
      clk      => clk,
      rst      => rst,
      ce       => ce,
      din      => din,
      tx_valid => tx_valid,
      tx_data  => tx_data,
      tx_ready => tx_ready,
      tx_done  => tx_done
    );

  ------------------------------------------------------------
  -- Sink VC (observe)
  ------------------------------------------------------------
  u_sink : entity work.StreamSink_VC
    generic map (MODEL_ID_NAME => "FIR_SINK")
    port map (
      clk      => clk,
      rst      => rst,
      ce_in    => ce,
      dout     => dout,
      rx_valid => rx_valid,
      rx_data  => rx_data,
      rx_ready => rx_ready
    );

  ------------------------------------------------------------
  -- Test controller (sequences + ref model + scoreboard + coverage)
  ------------------------------------------------------------
  u_ctrl : entity work.TestCtrl_fir
    port map (
      clk       => clk,
      rst       => rst,
      tx_valid  => tx_valid,
      tx_data   => tx_data,
      tx_ready  => tx_ready,
      tx_done   => tx_done,
      rx_valid  => rx_valid,
      rx_data   => rx_data,
      rx_ready  => rx_ready,
      test_done => test_done
    );

  ------------------------------------------------------------
  -- End of test
  ------------------------------------------------------------
  ControlProc : process
  begin
    wait until test_done;
    wait for 20 * tCLK;
    ReportAlerts;
    TranscriptClose;
    std.env.stop(0 when GetAlertCount = 0 else 1);
    wait;
  end process ControlProc;

end architecture test_harness;
