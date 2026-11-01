-- TbFIR_GoldenRobust.vhd
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.textio.all;

library osvvm;
context osvvm.OsvvmContext;

architecture GoldenRobust of TestCtrl is

  constant TEST_NAME    : string  := "TbFIR_GoldenRobust";
  constant FIR_LATENCY  : natural := 63;          -- <<< Adjust to your DUT
  constant INPUT_WIDTH  : natural := 16;
  constant OUTPUT_WIDTH : natural := 32;

  -- Scoreboard for expected results
  signal SB : ScoreboardIDType;

begin

  ------------------------------------------------------------
  -- Control Process
  ------------------------------------------------------------
  ControlProc : process
  begin
    SetTestName(TEST_NAME);
    SetLogEnable(PASSED, TRUE);

    -- Create scoreboard
    SB <= NewID("FIR_SB");

    wait until nReset = '1';
    WaitForClock(Clk, 5);

    WaitForBarrier(TestDone);                -- start stimulus
    WaitForBarrier(TestDone, 1 ms);          -- timeout

    AlertIf(now >= 1 ms, "Test timed out");
    AlertIf(GetAffirmCount < 1, "No checks performed");
    AlertIf(not Empty(SB), "Scoreboard not empty at end of test");

    EndOfTestReports;
    std.env.stop;
    wait;
  end process ControlProc;

  ------------------------------------------------------------
  -- Stimulus Process (reads files and pushes expected values)
  ------------------------------------------------------------
  StimProc : process
    file StimFile : text open read_mode is "stimuli.txt";   -- path here
    file ExpFile  : text open read_mode is "expected.txt";  -- path here

    variable L_stim, L_exp : line;
    variable Sample_in     : integer;
    variable Expected      : integer;
    variable good          : boolean;
    variable count         : natural := 0;
  begin
    WaitForBarrier(TestDone);

    -- Skip headers if present
    if not endfile(StimFile) then
      readline(StimFile, L_stim);
      if L_stim'length > 0 and L_stim.all(1) = '#' then
        readline(ExpFile, L_exp);
      end if;
    end if;

    while not endfile(StimFile) loop
      readline(StimFile, L_stim);
      read(L_stim, Sample_in, good);

      readline(ExpFile, L_exp);
      read(L_exp, Expected, good);

      count := count + 1;

      -- Push expected value into scoreboard FIRST
      Push(SB, Expected);

      -- Apply stimulus
      Sample      <= std_logic_vector(to_signed(Sample_in, INPUT_WIDTH));
      SampleValid <= '1';
      WaitForClock(Clk, 1);
    end loop;

    SampleValid <= '0';
    Log("Applied " & to_string(count) & " samples", INFO);

    -- Let the pipeline drain
    WaitForClock(Clk, FIR_LATENCY + 10);

    WaitForBarrier(TestDone);
    wait;
  end process StimProc;

  ------------------------------------------------------------
  -- Checker Process (accounts for latency)
  ------------------------------------------------------------
  CheckProc : process
    variable Received : integer;
    variable check_count : natural := 0;
  begin
    WaitForBarrier(TestDone);   -- synchronize start

    -- Wait for the FIR latency before starting to check
    WaitForClock(Clk, FIR_LATENCY);

    while True loop
      wait until rising_edge(Clk) and DUT_OutputValid = '1';

      Received := to_integer(signed(DUT_Output));

      -- Scoreboard check
      Check(SB, Received);

      check_count := check_count + 1;
    end loop;
  end process CheckProc;

end architecture GoldenRobust;