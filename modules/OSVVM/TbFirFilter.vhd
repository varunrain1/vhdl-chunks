library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

library osvvm;
context osvvm.OsvvmContext;

entity TbFirFilter is
end entity TbFirFilter;

architecture TestHarness of TbFirFilter is

  ------------------------------------------------------------
  -- Clock and Reset
  ------------------------------------------------------------
  constant tperiod_Clk : time := 10 ns;
  constant tpd         : time := 2 ns;   -- small propagation delay
  constant data_width  : positive := 16;
  constant acc_width   : positive := 32;
  constant coeff_width : positive := 16;
  constant taps        : positive := 16;
  
  signal Clk    : std_logic := '0';
  signal nReset : std_logic := '1';     -- active-low reset (common style)
  signal ce     : std_logic := '0';

  ------------------------------------------------------------
  -- DUT Interface Signals
  ------------------------------------------------------------
  signal din       : std_logic_vector(data_width-1 downto 0);
  signal dout      : std_logic_vector(acc_width-1 downto 0);

  ------------------------------------------------------------
  -- TestCtrl Interface
  -- (We will define the TestCtrl entity in the next step)
  ------------------------------------------------------------
  signal TestDone : std_logic := '0';       -- simple barrier / done flag

begin

  ------------------------------------------------------------
  -- Clock Generator
  ------------------------------------------------------------
  Clk <= not Clk after tperiod_Clk / 2;

  ------------------------------------------------------------
  -- Reset Generator (simple version)
  ------------------------------------------------------------
  process
  begin
    nReset <= '1';
    wait for 5 * tperiod_Clk;
    nReset <= '0';
    wait;
  end process;
  
  ------------------------------------------------------------
  -- control enable
  ------------------------------------------------------------
  process
  begin
    ce <= '0';
    wait for 5 * tperiod_Clk;
    ce <= '1';
    wait;
  end process;

  ------------------------------------------------------------
  -- DUT Instantiation
  -- (Replace Multiplier with your actual entity name if different)
  ------------------------------------------------------------
  DUT : entity work.e_fir_filter
  	generic map (
    	g_DATA_WIDTH => data_width,
        g_COEFF_WIDTH => coeff_width,
        g_TAPS => taps,
        g_ACC_WIDTH => acc_width
    port map (
      i_clk  => Clk,
      i_rst  => nReset,
      i_ce   => ce,
      i_din  => din,
      o_dout => dout
    );

  ------------------------------------------------------------
  -- TestCtrl Instantiation
  -- TestCtrl entity will be created next.
  -- We keep the instance name TestCtrl_1 (OSVVM convention)
  ------------------------------------------------------------
  TestCtrl_1 : entity work.TestCtrl
    generic map (
      tperiod_Clk => tperiod_Clk
    )
    port map (
      -- Clock and Reset
      Clk      => Clk,
      nReset   => nReset,
	  ce	   => ce,
      -- DUT Interface
      din        => din,
      dout  => dout,

      -- Synchronization
      TestDone => TestDone
    );

end architecture TestHarness;