library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity pi_filter is
    generic (
        W_ERROR     : integer := 2;          -- width of early/late error
        W_PROP      : integer := 8;          -- proportional gain width
        W_INTEG     : integer := 16;         -- integral accumulator width
        W_OUT       : integer := 16;         -- filter output width (to NCO)
        KP          : integer := 4;          -- proportional gain (shift)
        KI          : integer := 8           -- integral gain (shift)
    );
    port (
        clk         : in  std_logic;
        rst         : in  std_logic;
        early       : in  std_logic;
        late        : in  std_logic;
        transition  : in  std_logic;
        filter_out  : out signed(W_OUT-1 downto 0)
    );
end entity;

architecture rtl of pi_filter is
    signal error      : signed(W_ERROR-1 downto 0) := (others => '0');
    signal prop       : signed(W_OUT-1 downto 0) := (others => '0');
    signal integ_acc  : signed(W_INTEG-1 downto 0) := (others => '0');
    signal integ      : signed(W_OUT-1 downto 0) := (others => '0');
begin
    process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                error     <= (others => '0');
                prop      <= (others => '0');
                integ_acc <= (others => '0');
                integ     <= (others => '0');
                filter_out<= (others => '0');
            else
                -- Error: +1 = late, -1 = early, 0 = no transition
                if transition = '1' then
                    if late = '1' then
                        error <= to_signed(1, W_ERROR);
                    elsif early = '1' then
                        error <= to_signed(-1, W_ERROR);
                    else
                        error <= (others => '0');
                    end if;
                else
                    error <= (others => '0');
                end if;

                -- Proportional path
                prop <= resize(error, W_OUT) sll KP;

                -- Integral path
                integ_acc <= integ_acc + resize(error, W_INTEG);
                integ     <= resize(integ_acc, W_OUT) sll KI;

                -- PI output
                filter_out <= prop + integ;
            end if;
        end if;
    end process;
end architecture;