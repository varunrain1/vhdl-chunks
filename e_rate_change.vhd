library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity e_rate_change is
  generic (
    g_DATA_WIDTH : positive := 16;
    g_FACTOR     : positive := 4;
    g_MODE       : string   := "DOWN"          -- "UP" or "DOWN"
  );
  port (
    i_clk  : in  std_logic;
    i_rst     : in  std_logic;                 -- asynchronous reset
    i_ce   : in  std_logic;
    i_din     : in  signed(g_DATA_WIDTH-1 downto 0);
    o_clk : in  std_logic;
    o_ce  : out std_logic;
    o_dout    : out signed(g_DATA_WIDTH-1 downto 0)
  );
end entity;

architecture rtl of e_rate_change is
  signal s_cnt    : integer range 0 to g_FACTOR-1 := 0;
  signal s_sample : signed(g_DATA_WIDTH-1 downto 0) := (others => '0');
  signal s_ce_int : std_logic := '0';
begin
  gen_down : if g_MODE = "DOWN" generate
    process(i_clk, i_rst)
    begin
      if i_rst = '1' then
        s_cnt    <= 0;
        s_ce_int <= '0';
        s_sample <= (others => '0');
      elsif rising_edge(i_clk) then
        if i_ce = '1' then
          if s_cnt = g_FACTOR-1 then
            s_cnt    <= 0;
            s_ce_int <= '1';
            s_sample <= i_din;
          else
            s_cnt    <= s_cnt + 1;
            s_ce_int <= '0';
          end if;
        else
          s_ce_int <= '0';
        end if;
      end if;
    end process;
    o_dout   <= s_sample;
    o_ce <= s_ce_int;
  end generate;

  gen_up : if g_MODE = "UP" generate
    process(i_clk, i_rst)
    begin
      if i_rst = '1' then
        s_cnt    <= 0;
        s_sample <= (others => '0');
        s_ce_int <= '0';
      elsif rising_edge(i_clk) then
        if i_ce = '1' then
          s_sample <= i_din;
          s_cnt    <= 0;
          s_ce_int <= '1';
        else
          if s_cnt < g_FACTOR-1 then
            s_cnt    <= s_cnt + 1;
            s_ce_int <= '1';
            s_sample <= (others => '0');   -- zero-stuffing
          else
            s_ce_int <= '0';
          end if;
        end if;
      end if;
    end process;
    o_dout   <= s_sample;
    o_ce <= s_ce_int;
  end generate;
end architecture;