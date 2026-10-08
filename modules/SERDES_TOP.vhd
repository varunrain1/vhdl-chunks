library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.SERDES_PKG.all;
Library UNISIM;
use UNISIM.vcomponents.all;

entity SERDES_TOP is
    Port ( CLK_I : in STD_LOGIC;
           CLK_DIV_I : in std_logic;
           RST_I : in STD_LOGIC;
           CS_N_I : in std_logic;
           WR_EN_I : in std_logic;
           RD_EN_I : in std_logic;
           DATA_I : in std_logic_vector(C_DATA_WIDTH - 1 downto 0);
           DATA_O : out std_logic);
end SERDES_TOP;

architecture RTL of SERDES_TOP is


component SERDES_DATA_HANDLE is
    port (CLK_I : in STD_LOGIC;
           RST_I : in STD_LOGIC;
           CS_N_I : in std_logic;
           DATA_I : in std_logic;
           DATA_O : out std_logic
           );
end component SERDES_DATA_HANDLE;

component CDC_FIFO is
    generic (
            C_FIFO_DEPTH : integer := 16;
            C_COUNTER_WIDTH : integer := 5;
            C_DATA_WIDTH : integer := 8
            );
    Port ( CLK_WR_I : in STD_LOGIC;
           RST_WR_I : in STD_LOGIC;
           WR_EN_I  : in std_logic;
           DATA_I   : in std_logic_vector(C_DATA_WIDTH - 1 downto 0);
           CLK_RD_I : in std_logic;
           RST_RD_I : in std_logic;
           RD_EN_I  : in std_logic;
           DATA_VALID : out std_logic;
           DATA_O   : out std_logic_vector(C_DATA_WIDTH - 1 downto 0)
           );
end component CDC_FIFO;

constant C_FIFO_DEPTH : integer := 16;
constant C_COUNTER_WIDTH : integer := 5;
constant C_DATA_WIDTH : integer := 8;

signal S_DATA_PAR : std_logic_vector(C_DATA_WIDTH - 1 downto 0);
signal S_DATA_SER, S_DATA : std_logic;
signal S_CLK : std_logic;
signal S_COUNT : integer;
signal S_DATA_VALID : std_logic;

begin

            
    SERDES_DATA : SERDES_DATA_HANDLE
        port map(
                CLK_I => CLK_I,
                RST_I => RST_I,
                CS_N_I => CS_N_I,
                DATA_I => S_DATA_SER,
                DATA_O => S_DATA
                );
    
   FIFO_CDC : CDC_FIFO
        generic map(
                    C_FIFO_DEPTH => C_FIFO_DEPTH,
                    C_COUNTER_WIDTH => C_COUNTER_WIDTH,
                    C_DATA_WIDTH => C_DATA_WIDTH)
        port map(
                    CLK_WR_I    => CLK_DIV_I,
                    RST_WR_I    => RST_I,
                    WR_EN_I     => WR_EN_I,
                    DATA_I      => DATA_I,
                    CLK_RD_I    => CLK_I,
                    RST_RD_I    => RST_I,
                    RD_EN_I     => RD_EN_I,
                    DATA_VALID  => S_DATA_VALID,
                    DATA_O      => S_DATA_PAR
                    );
                    
  
    
DATA_O <= S_DATA;

S_CLK <= CLK_I;


P_SERIALIZE : process(S_CLK, RST_I)
begin
    if RST_I = '1' then
        S_DATA_SER <= '0';
        S_COUNT <= 7;
    elsif S_COUNT > 0 and S_DATA_VALID = '1' then
        if S_CLK = '1' then
            S_DATA_SER <= S_DATA_PAR(S_COUNT);
            S_COUNT <= S_COUNT - 1;
        else 
            S_DATA_SER <= S_DATA_PAR(S_COUNT);
            S_COUNT <= S_COUNT - 1;
        end if;
    elsif S_COUNT = 0 and S_DATA_VALID = '1' then
        S_DATA_SER <= S_DATA_PAR(S_COUNT);
        S_COUNT <= 7;    
    else
        S_COUNT <= 7;
    end if;
end process P_SERIALIZE;

end RTL;
