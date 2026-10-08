library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity phase_detector is
    port (
        clk          : in  std_logic;                     -- high-speed sampling clock (from NCO)
        rst          : in  std_logic;
        data_in      : in  std_logic;                     -- serial data
        early        : out std_logic;                     -- data transition is early
        late         : out std_logic;                     -- data transition is late
        transition   : out std_logic                      -- valid transition detected
    );
end entity;

architecture rtl of phase_detector is
    signal d0, d1, d2 : std_logic := '0';  -- three samples: previous, edge, current
begin
    process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                d0 <= '0';
                d1 <= '0';
                d2 <= '0';
            else
                d0 <= d1;
                d1 <= d2;
                d2 <= data_in;
            end if;
        end if;
    end process;

    -- Transition detection and early/late decision
    transition <= d0 xor d2;                 -- transition occurred between samples
    early      <= (d0 xor d1) and transition; -- edge sample different from previous → early
    late       <= (d1 xor d2) and transition; -- edge sample different from current  → late
end architecture;