library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

package SERDES_PKG is 
    
   constant C_DATA_WIDTH : integer := 8;
   constant C_PRE_DATA_LEN : integer := 24;
   constant C_POST_DATA_LEN : integer := 16;
   constant C_ARRAY_WIDTH : integer := 32;
   
   constant C_DATA_NULL : std_logic_vector(C_PRE_DATA_LEN - 1 downto 0) := x"000000";
   constant C_DATA_SEQ : std_logic_vector(C_DATA_WIDTH - 1 downto 0) := x"B8";
   
   constant C_DATA_SYNC : std_logic_vector(C_ARRAY_WIDTH - 1 downto 0) := x"000000B8";
   
end package SERDES_PKG;