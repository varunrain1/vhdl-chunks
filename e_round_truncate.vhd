library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity e_round_truncate is
  generic (
    g_IN_WIDTH   : positive := 24;
    g_OUT_WIDTH  : positive := 16;
    g_ROUND_MODE : string   := "ROUND_HALF_UP"
  );
  port (
    i_din  : in  signed(g_IN_WIDTH-1 downto 0);
    o_dout : out signed(g_OUT_WIDTH-1 downto 0)
  );
end entity;

architecture rtl of e_round_truncate is
  constant c_FRAC_BITS : integer := g_IN_WIDTH - g_OUT_WIDTH;
begin
  process(all)
    variable truncated : signed(g_OUT_WIDTH-1 downto 0);
    variable round_bit : std_logic;
  begin
    if c_FRAC_BITS <= 0 then
      o_dout <= resize(i_din, g_OUT_WIDTH);
    else
      truncated := i_din(g_IN_WIDTH-1 downto c_FRAC_BITS);
      round_bit := i_din(c_FRAC_BITS-1);

      if g_ROUND_MODE = "TRUNCATE" then
        o_dout <= truncated;
      else
        if round_bit = '1' then
          o_dout <= truncated + 1;
        else
          o_dout <= truncated;
        end if;
      end if;
    end if;
  end process;
end architecture;