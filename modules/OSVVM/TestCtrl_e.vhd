-- TestCtrl_e.vhd
-- TestCtrl entity for FIR filter testbench (golden vector version)

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library osvvm;
context osvvm.OsvvmContext;

entity TestCtrl is
  generic (
    tperiod_Clk : time := 10 ns
  );
  port (
    -------------------------------------------------------
    -- Clock and Reset
    -------------------------------------------------------
    Clk            : in  std_logic;
    nReset         : in  std_logic;

    -------------------------------------------------------
    -- DUT Interface (Stimulus side)
    -------------------------------------------------------
    Sample         : out std_logic_vector(15 downto 0);  -- Input sample to FIR
    SampleValid    : out std_logic;

    -------------------------------------------------------
    -- DUT Interface (Result side)
    -------------------------------------------------------
    DUT_Output     : in  std_logic_vector(31 downto 0);  -- FIR output
    DUT_OutputValid: in  std_logic;

    -------------------------------------------------------
    -- Synchronization
    -------------------------------------------------------
    TestDone       : inout std_logic
  );
end entity TestCtrl;