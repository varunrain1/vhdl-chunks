library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity e_complex_arith is
  generic (
    g_DATA_WIDTH : positive := 16
  );
  port (
    i_clk        : in  std_logic;
    i_rst        : in  std_logic;                     -- asynchronous reset
    i_ce         : in  std_logic;
    i_a_re, i_a_im : in  signed(g_DATA_WIDTH-1 downto 0);
    i_b_re, i_b_im : in  signed(g_DATA_WIDTH-1 downto 0);
    i_op         : in  std_logic_vector(1 downto 0);  -- 00=add, 01=sub, 10=mul
    o_y_re, o_y_im : out signed(2*g_DATA_WIDTH downto 0)
  );
end entity;

architecture rtl of e_complex_arith is
  signal s_re, s_im : signed(2*g_DATA_WIDTH downto 0);
begin
  process(i_clk, i_rst)
  begin
    if i_rst = '1' then
      s_re <= (others => '0');
      s_im <= (others => '0');
    elsif rising_edge(i_clk) then
      if i_ce = '1' then
        case i_op is
          when "00" =>  -- add
            s_re <= resize(i_a_re, 2*g_DATA_WIDTH+1) + resize(i_b_re, 2*g_DATA_WIDTH+1);
            s_im <= resize(i_a_im, 2*g_DATA_WIDTH+1) + resize(i_b_im, 2*g_DATA_WIDTH+1);
          when "01" =>  -- sub
            s_re <= resize(i_a_re, 2*g_DATA_WIDTH+1) - resize(i_b_re, 2*g_DATA_WIDTH+1);
            s_im <= resize(i_a_im, 2*g_DATA_WIDTH+1) - resize(i_b_im, 2*g_DATA_WIDTH+1);
          when "10" =>  -- multiply
            s_re <= resize(i_a_re * i_b_re - i_a_im * i_b_im, 2*g_DATA_WIDTH+1);
            s_im <= resize(i_a_re * i_b_im + i_a_im * i_b_re, 2*g_DATA_WIDTH+1);
          when others =>
            s_re <= (others => '0');
            s_im <= (others => '0');
        end case;
      end if;
    end if;
  end process;
  o_y_re <= s_re;
  o_y_im <= s_im;
end architecture;