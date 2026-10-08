library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.SERDES_PKG.all;

entity SERDES_DATA_HANDLE is
    Port ( CLK_I : in STD_LOGIC;
           RST_I : in STD_LOGIC;
           CS_N_I : in std_logic;
           DATA_I : in std_logic;
           DATA_O : out std_logic
           );
end SERDES_DATA_HANDLE;

architecture RTL of SERDES_DATA_HANDLE is

signal S_SEQ_ARR : std_logic_vector(C_ARRAY_WIDTH - 1 downto 0);
signal S_SEQ_DETECT : std_logic;
signal S_DATA_SER : std_logic;
signal S_CLK : std_logic;

begin

S_CLK <= CLK_I;

P_DATA_LOAD : process(S_CLK,RST_I)
begin
    if RST_I = '1' then
        S_SEQ_ARR <= (others => '0');    
    elsif CS_N_I = '0' then
        if S_CLK = '1' then 
            S_SEQ_ARR <= S_SEQ_ARR(C_ARRAY_WIDTH - 2 downto 0) & DATA_I;
        else    
            S_SEQ_ARR <= S_SEQ_ARR(C_ARRAY_WIDTH - 2 downto 0) & DATA_I;
        end if;
    end if;
end process P_DATA_LOAD;

S_SEQ_DETECT <= '1' when S_SEQ_ARR = C_DATA_SYNC;

S_DATA_SER <= S_SEQ_ARR(0) when S_SEQ_DETECT = '1';

DATA_O <= S_DATA_SER;

end RTL;
