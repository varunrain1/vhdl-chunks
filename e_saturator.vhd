library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity e_saturator is
  generic (
    g_IN_WIDTH  : positive := 20;
    g_OUT_WIDTH : positive := 16
  );
  port (
    i_din  : in  signed(g_IN_WIDTH-1 downto 0);
    o_dout : out signed(g_OUT_WIDTH-1 downto 0)
  );
end entity;

architecture rtl of e_saturator is
  constant c_MAX_POS : signed(g_OUT_WIDTH-1 downto 0) := (g_OUT_WIDTH-1 => '0', others => '1');
  constant c_MAX_NEG : signed(g_OUT_WIDTH-1 downto 0) := (g_OUT_WIDTH-1 => '1', others => '0');
begin
  process(all)
  begin
    if i_din > resize(c_MAX_POS, g_IN_WIDTH) then
      o_dout <= c_MAX_POS;
    elsif i_din < resize(c_MAX_NEG, g_IN_WIDTH) then
      o_dout <= c_MAX_NEG;
    else
      o_dout <= resize(i_din, g_OUT_WIDTH);
    end if;
  end process;
end architecture;