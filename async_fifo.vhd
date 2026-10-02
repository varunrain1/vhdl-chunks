library ieee;

use ieee.std_logic_1164.all;
use ieee.numeric_std.all;


entity async_fifo is
    generic (
        DATA_WIDTH : positive := 32;
        ADDR_WIDTH : positive := 4
    );
    port (
        -- Write clock domain
        wr_clk   : in  std_logic;
        wr_rst_n : in  std_logic;
        wr_en    : in  std_logic;
        wr_data  : in  std_logic_vector(DATA_WIDTH-1 downto 0);
        full     : out std_logic;

        -- Read clock domain
        rd_clk   : in  std_logic;
        rd_rst_n : in  std_logic;
        rd_en    : in  std_logic;
        rd_data  : out std_logic_vector(DATA_WIDTH-1 downto 0);
        empty    : out std_logic
    );
end entity;


architecture rtl of async_fifo is

    --------------------------------------------------------------------
    -- Constants
    --------------------------------------------------------------------

    constant PTR_WIDTH : positive := ADDR_WIDTH + 1;


    --------------------------------------------------------------------
    -- FIFO memory
    --------------------------------------------------------------------

    type ram_type is array (
        0 to (2**ADDR_WIDTH)-1
    ) of std_logic_vector(DATA_WIDTH-1 downto 0);

    signal ram : ram_type;


    --------------------------------------------------------------------
    -- Binary pointers
    --------------------------------------------------------------------

    signal wr_bin      : unsigned(PTR_WIDTH-1 downto 0);
    signal wr_bin_next : unsigned(PTR_WIDTH-1 downto 0);

    signal rd_bin      : unsigned(PTR_WIDTH-1 downto 0);
    signal rd_bin_next : unsigned(PTR_WIDTH-1 downto 0);


    --------------------------------------------------------------------
    -- Gray-coded pointers
    --------------------------------------------------------------------

    signal wr_gray      : unsigned(PTR_WIDTH-1 downto 0);
    signal wr_gray_next : unsigned(PTR_WIDTH-1 downto 0);

    signal rd_gray      : unsigned(PTR_WIDTH-1 downto 0);
    signal rd_gray_next : unsigned(PTR_WIDTH-1 downto 0);


    --------------------------------------------------------------------
    -- Synchronizers
    --
    -- Write pointer synchronized into read clock domain
    --------------------------------------------------------------------

    signal wr_gray_sync1 : unsigned(PTR_WIDTH-1 downto 0);
    signal wr_gray_sync2 : unsigned(PTR_WIDTH-1 downto 0);


    --------------------------------------------------------------------
    -- Read pointer synchronized into write clock domain
    --------------------------------------------------------------------

    signal rd_gray_sync1 : unsigned(PTR_WIDTH-1 downto 0);
    signal rd_gray_sync2 : unsigned(PTR_WIDTH-1 downto 0);


    --------------------------------------------------------------------
    -- Internal status signals
    --------------------------------------------------------------------

    signal full_i  : std_logic;
    signal empty_i : std_logic;


    --------------------------------------------------------------------
    -- Reset synchronizers
    --------------------------------------------------------------------

    signal wr_rst_sync : std_logic_vector(1 downto 0);
    signal rd_rst_sync : std_logic_vector(1 downto 0);

    signal wr_local_rst_n : std_logic;
    signal rd_local_rst_n : std_logic;


    --------------------------------------------------------------------
    -- Functions
    --------------------------------------------------------------------

    function binary_to_gray(
        binary : unsigned
    ) return unsigned is
    begin
        return binary xor (binary srl 1);
    end function;


    function gray_to_binary(
        gray : unsigned
    ) return unsigned is

        variable binary : unsigned(gray'range);

    begin

        binary(binary'high) := gray(gray'high);

        for i in binary'high-1 downto binary'low loop
            binary(i) := binary(i+1) xor gray(i);
        end loop;

        return binary;

    end function;


begin

    --------------------------------------------------------------------
    -- Parameter checking
    --------------------------------------------------------------------

    assert ADDR_WIDTH >= 2
        report "ADDR_WIDTH must be >= 2"
        severity failure;


    --------------------------------------------------------------------
    -- Local reset synchronizer for WRITE domain
    --
    -- Asynchronous assertion
    -- Synchronous deassertion
    --------------------------------------------------------------------

    process(wr_clk, wr_rst_n)
    begin

        if wr_rst_n = '0' then

            wr_rst_sync <= (others => '0');

        elsif rising_edge(wr_clk) then

            wr_rst_sync(0) <= '1';
            wr_rst_sync(1) <= wr_rst_sync(0);

        end if;

    end process;

    wr_local_rst_n <= wr_rst_sync(1);


    --------------------------------------------------------------------
    -- Local reset synchronizer for READ domain
    --
    -- Asynchronous assertion
    -- Synchronous deassertion
    --------------------------------------------------------------------

    process(rd_clk, rd_rst_n)
    begin

        if rd_rst_n = '0' then

            rd_rst_sync <= (others => '0');

        elsif rising_edge(rd_clk) then

            rd_rst_sync(0) <= '1';
            rd_rst_sync(1) <= rd_rst_sync(0);

        end if;

    end process;

    rd_local_rst_n <= rd_rst_sync(1);


    --------------------------------------------------------------------
    -- Write pointer
    --------------------------------------------------------------------

    process(wr_clk, wr_local_rst_n)
    begin

        if wr_local_rst_n = '0' then

            wr_bin  <= (others => '0');
            wr_gray <= (others => '0');

        elsif rising_edge(wr_clk) then

            wr_bin  <= wr_bin_next;
            wr_gray <= wr_gray_next;

        end if;

    end process;


    --------------------------------------------------------------------
    -- Calculate next write pointer
    --------------------------------------------------------------------

    process(all)
    begin

        wr_bin_next <= wr_bin;

        if (wr_en = '1') and (full_i = '0') then

            wr_bin_next <= wr_bin + 1;

        end if;

        wr_gray_next <= binary_to_gray(wr_bin_next);

    end process;


    --------------------------------------------------------------------
    -- Write data into RAM
    --------------------------------------------------------------------

    process(wr_clk)
    begin

        if rising_edge(wr_clk) then

            if (wr_en = '1') and (full_i = '0') then

                ram(to_integer(wr_bin(ADDR_WIDTH-1 downto 0)))
                    <= wr_data;

            end if;

        end if;

    end process;


    --------------------------------------------------------------------
    -- Synchronize READ pointer into WRITE domain
    --------------------------------------------------------------------

    process(wr_clk, wr_local_rst_n)
    begin

        if wr_local_rst_n = '0' then

            rd_gray_sync1 <= (others => '0');
            rd_gray_sync2 <= (others => '0');

        elsif rising_edge(wr_clk) then

            rd_gray_sync1 <= rd_gray;
            rd_gray_sync2 <= rd_gray_sync1;

        end if;

    end process;


    --------------------------------------------------------------------
    -- FULL generation
    --------------------------------------------------------------------
    --
    -- FIFO is full when the NEXT write pointer catches the read pointer
    -- with the two MSBs inverted in Gray-code space.
    --------------------------------------------------------------------

    process(all)

        variable rd_gray_full_compare :
            unsigned(PTR_WIDTH-1 downto 0);

    begin

        rd_gray_full_compare := rd_gray_sync2;

        rd_gray_full_compare(PTR_WIDTH-1) :=
            not rd_gray_sync2(PTR_WIDTH-1);

        rd_gray_full_compare(PTR_WIDTH-2) :=
            not rd_gray_sync2(PTR_WIDTH-2);

        if wr_gray_next = rd_gray_full_compare then

            full_i <= '1';

        else

            full_i <= '0';

        end if;

    end process;

    full <= full_i;


    --------------------------------------------------------------------
    -- Read pointer
    --------------------------------------------------------------------

    process(rd_clk, rd_local_rst_n)
    begin

        if rd_local_rst_n = '0' then

            rd_bin  <= (others => '0');
            rd_gray <= (others => '0');

        elsif rising_edge(rd_clk) then

            rd_bin  <= rd_bin_next;
            rd_gray <= rd_gray_next;

        end if;

    end process;


    --------------------------------------------------------------------
    -- Calculate next read pointer
    --------------------------------------------------------------------

    process(all)
    begin

        rd_bin_next <= rd_bin;

        if (rd_en = '1') and (empty_i = '0') then

            rd_bin_next <= rd_bin + 1;

        end if;

        rd_gray_next <= binary_to_gray(rd_bin_next);

    end process;


    --------------------------------------------------------------------
    -- Synchronize WRITE pointer into READ domain
    --------------------------------------------------------------------

    process(rd_clk, rd_local_rst_n)
    begin

        if rd_local_rst_n = '0' then

            wr_gray_sync1 <= (others => '0');
            wr_gray_sync2 <= (others => '0');

        elsif rising_edge(rd_clk) then

            wr_gray_sync1 <= wr_gray;
            wr_gray_sync2 <= wr_gray_sync1;

        end if;

    end process;


    --------------------------------------------------------------------
    -- EMPTY generation
    --------------------------------------------------------------------

    process(all)
    begin

        if rd_gray_next = wr_gray_sync2 then

            empty_i <= '1';

        else

            empty_i <= '0';

        end if;

    end process;

    empty <= empty_i;


    --------------------------------------------------------------------
    -- Read data
    --------------------------------------------------------------------

    process(rd_clk, rd_local_rst_n)
    begin

        if rd_local_rst_n = '0' then

            rd_data <= (others => '0');

        elsif rising_edge(rd_clk) then

            if (rd_en = '1') and (empty_i = '0') then

                rd_data <= ram(
                    to_integer(rd_bin(ADDR_WIDTH-1 downto 0))
                );

            end if;

        end if;

    end process;


end architecture;