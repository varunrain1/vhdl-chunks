library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity e_comparator is
  generic (
    g_DATA_WIDTH  : positive := 16;
    g_SIGNED_MODE : boolean  := true
  );
  port (
    a, b   : in  std_logic_vector(g_DATA_WIDTH-1 downto 0);
    a_gt_b : out std_logic;
    a_eq_b : out std_logic;
    a_lt_b : out std_logic
  );
end entity;

architecture rtl of e_comparator is
begin
  gen_signed : if g_SIGNED_MODE generate
    a_gt_b <= '1' when signed(a) >  signed(b) else '0';
    a_eq_b <= '1' when signed(a) =  signed(b) else '0';
    a_lt_b <= '1' when signed(a) <  signed(b) else '0';
  end generate;

  gen_unsigned : if not g_SIGNED_MODE generate
    a_gt_b <= '1' when unsigned(a) >  unsigned(b) else '0';
    a_eq_b <= '1' when unsigned(a) =  unsigned(b) else '0';
    a_lt_b <= '1' when unsigned(a) <  unsigned(b) else '0';
  end generate;
end architecture;