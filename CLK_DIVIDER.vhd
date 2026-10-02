library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity CLK_DIVIDER is
    generic (
            G_N : integer := 5;
            G_I_F : integer := 1;
            G_DUTY_CYCLE: integer := 50
            );
    Port ( CLK_I : in STD_LOGIC;
           RST_I : in STD_LOGIC;
           CLK_O : out std_logic);
end CLK_DIVIDER;

architecture RTL of CLK_DIVIDER is

constant C_DUTY_CYLE : integer := 20;
signal S_RNG_CNTR : std_logic_vector(G_N -1 downto 0);
signal S_DLY : std_logic_vector(3 downto 0);
signal S_SIG_DLY_1, S_SIG_DLY_2 : std_logic;
signal S_SIG_DLY_POS: std_logic;
signal S_SIG_DLY_NEG: std_logic;
signal S_CLK_DIV : std_logic;

begin

P_RNG_CNTR : process(RST_I, CLK_I)
begin
    if RST_I = '1' then
        S_RNG_CNTR <= (others => '0');
        S_RNG_CNTR(4) <= '1';
    elsif rising_edge(CLK_I) then
        S_RNG_CNTR <= S_RNG_CNTR(G_N - 2 downto 0) & S_RNG_CNTR(G_N - 1);
    end if;
end process P_RNG_CNTR;

P_CLK_DELAY : process(RST_I, CLK_I)
begin
    if RST_I = '1' then
        S_DLY <= (others => '0');
    elsif falling_edge(CLK_I) then
        case G_DUTY_CYCLE is
            when 10 =>
                S_DLY(0) <= S_RNG_CNTR(0);
            when 50 =>
                S_DLY(1) <= S_RNG_CNTR(1);
            when 70 =>
                S_DLY(2) <= S_RNG_CNTR(2);
            when 90 =>
                S_DLY(3) <= S_RNG_CNTR(3);
            when others =>
                S_DLY <= (others => '0');
        end case;
    end if;
end process P_CLK_DELAY;

S_CLK_DIV <= S_RNG_CNTR(0) or S_RNG_CNTR(1) or S_DLY(1) when G_DUTY_CYCLE = 50 else
         S_RNG_CNTR(0) and S_DLY(0) when G_DUTY_CYCLE = 10 else
         S_RNG_CNTR(0) or S_DLY(0) when G_DUTY_CYCLE = 30 else
         S_RNG_CNTR(0) when G_DUTY_CYCLE = 20 else 
         S_RNG_CNTR(0) or S_RNG_CNTR(1) when G_DUTY_CYCLE = 40 else
         S_RNG_CNTR(0) or S_RNG_CNTR(1) or S_RNG_CNTR(2) when G_DUTY_CYCLE = 60 else
         S_RNG_CNTR(0) or S_RNG_CNTR(1) or S_RNG_CNTR(2) or S_DLY(2) when G_DUTY_CYCLE = 70 else
         S_RNG_CNTR(0) or S_RNG_CNTR(1) or S_RNG_CNTR(2) or S_RNG_CNTR(3) when G_DUTY_CYCLE = 80 else
         S_RNG_CNTR(0) or S_RNG_CNTR(1) or S_RNG_CNTR(2) or S_RNG_CNTR(3) or S_DLY(3);

P_SIG_DELAY_POS : process(CLK_I, RST_I)
begin
    if RST_I = '1' then
        S_SIG_DLY_POS <= '0';
    elsif rising_edge(CLK_I) then
        S_SIG_DLY_POS <= S_CLK_DIV;
--        S_SIG_DLY_40_60 <= S_SIG_DLY_POS or S_SIG_DLY;
    end if;
end process P_SIG_DELAY_POS;

P_SIG_DELAY_NEG : process(CLK_I, RST_I)
begin
    if RST_I = '1' then
        S_SIG_DLY_NEG <= '0';
    elsif falling_edge(CLK_I) then
        S_SIG_DLY_NEG <= S_CLK_DIV;
--        S_SIG_DLY_20_80 <= S_SIG_DLY_NEG or S_SIG_DLY;
    end if;
end process P_SIG_DELAY_NEG;

S_SIG_DLY_1 <= S_SIG_DLY_POS when CLK_I = '1' else
             S_SIG_DLY_NEG when CLK_I = '0';
S_SIG_DLY_2 <= S_SIG_DLY_POS when CLK_I = '0' else
             S_SIG_DLY_NEG when CLK_I = '1';

CLK_O <= S_CLK_DIV xor S_SIG_DLY_1 when C_DUTY_CYLE = 20 and G_I_F = 0 else
         S_CLK_DIV xor S_SIG_DLY_2 when C_DUTY_CYLE = 40 and G_I_F = 0 else
         not(S_CLK_DIV xor S_SIG_DLY_2) when C_DUTY_CYLE = 60 and G_I_F = 0 else
         not(S_CLK_DIV xor S_SIG_DLY_1) when C_DUTY_CYLE = 80 and G_I_F = 0 else
         S_CLK_DIV when G_I_F = 1 else
         '0';
end RTL;
