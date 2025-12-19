import {
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useContext, useEffect, useMemo, useState } from "react";
import { UserContext } from "../context/UserContext";
import { tokens } from "../theme";
import { API_BASE } from "../config";

const ORDERS_STORAGE_KEY = "smmstore.orders";



const Smmstore = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const { user } = useContext(UserContext);
  const [balance, setBalance] = useState(null);
  const [balanceCurrency, setBalanceCurrency] = useState("");
  const [balanceError, setBalanceError] = useState("");
  const [loadingBalance, setLoadingBalance] = useState(false);

  const apiKey = user?.smmstore_api_key || "";
  const hasKey = useMemo(() => apiKey.trim().length > 0, [apiKey]);

  const [servicesByCategory, setServicesByCategory] = useState({});
  const [category, setCategory] = useState("");
  const [service, setService] = useState("");
  const [serviceIdMap, setServiceIdMap] = useState({});
  const [search, setSearch] = useState("");
  const [link, setLink] = useState("");
  const [quantity, setQuantity] = useState("1000");
  const [runDate, setRunDate] = useState(() =>
    new Date().toISOString().slice(0, 10)
  );
  const [runTime, setRunTime] = useState(() => {
    const now = new Date();
    return `${String(now.getHours()).padStart(2, "0")}:${String(
      now.getMinutes()
    ).padStart(2, "0")}`;
  });
  const [dripFeed, setDripFeed] = useState(false);
  const [runs, setRuns] = useState("");
  const [interval, setInterval] = useState("");
  const [orders, setOrders] = useState([]);
  const [orderError, setOrderError] = useState("");
  const [loadingServices, setLoadingServices] = useState(false);

  const apiRequest = async (endpoint, payload, signal) => {
    if (!hasKey) {
      return { error: "Missing API key. Set it in Profile." };
    }
    const token = localStorage.getItem("access_token");
    try {
      const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload || {}),
        signal,
      });
      const data = await resp.json();
      if (!resp.ok) {
        return { error: data?.detail || data?.error || "Request failed" };
      }
      return data;
    } catch (err) {
      if (err?.name === "AbortError") return { error: "aborted" };
      return { error: err?.message || "Request failed" };
    }
  };

  const fetchBalance = async (signal) => {
    if (!hasKey) return;
    setLoadingBalance(true);
    setBalanceError("");

    try {
      const data = await apiRequest("/api/smmstore/balance", {}, signal);
      if (data?.error) throw new Error(data.error);

      const value = data?.balance ?? null;
      setBalance(value !== null ? Number(value) : null);
      setBalanceCurrency(data?.currency || "");
    } catch (err) {
      if (err?.name === "AbortError") return;
      setBalance(null);
      setBalanceCurrency("");
      setBalanceError(err?.message || "Unable to load balance");
    } finally {
      setLoadingBalance(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    fetchBalance(controller.signal);
    return () => controller.abort();
  }, [apiKey, hasKey]);

  useEffect(() => {
    const controller = new AbortController();
    const loadServices = async () => {
      if (!hasKey) return;
      setLoadingServices(true);
      const data = await apiRequest("/api/smmstore/services", {}, controller.signal);
      if (data?.error || data === "aborted") {
        setLoadingServices(false);
        return;
      }
      const list = Array.isArray(data) ? data : data?.services || [];
      const grouped = {};
      const idMap = {};
      list.forEach((item) => {
        const cat = item?.category || "Unknown";
        grouped[cat] = grouped[cat] || [];
        grouped[cat].push(item);
        const label = `${item.service} - ${item.name}`;
        idMap[label] = item.service;
      });
      setServicesByCategory(grouped);
      setServiceIdMap(idMap);
      const firstCat = Object.keys(grouped)[0] || "";
      setCategory(firstCat);
      if (firstCat && grouped[firstCat]?.length) {
        const firstLabel = `${grouped[firstCat][0].service} - ${grouped[firstCat][0].name}`;
        setService(firstLabel);
        setSearch(firstLabel);
      }
      setLoadingServices(false);
    };
    loadServices();
    return () => controller.abort();
  }, [apiKey, hasKey]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(ORDERS_STORAGE_KEY);
      setOrders(raw ? JSON.parse(raw) : []);
    } catch {
      setOrders([]);
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(ORDERS_STORAGE_KEY, JSON.stringify(orders));
    } catch {
      // ignore storage errors
    }
  }, [orders]);

  const filteredServices = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return [];
    const results = [];
    Object.values(servicesByCategory).forEach((items) => {
      items.forEach((item) => {
        const label = `${item.service} - ${item.name}`;
        if (
          String(item.service).toLowerCase().includes(keyword) ||
          item.name?.toLowerCase().includes(keyword)
        ) {
          results.push(label);
        }
      });
    });
    return results.slice(0, 100);
  }, [search, servicesByCategory]);

  const handleSelectService = (label) => {
    setService(label);
    setSearch(label);
  };

  const buildRunAt = () => {
    if (!runDate || !runTime) return new Date();
    return new Date(`${runDate}T${runTime}:00`);
  };

  const addOrderToQueue = (data) => {
    setOrders((prev) => [...prev, data]);
  };

  const updateOrder = (id, changes) => {
    setOrders((prev) =>
      prev.map((order) => (order.id === id ? { ...order, ...changes } : order))
    );
  };

  const sendOrder = async (order) => {
    const params = {
      action: "add",
      service: order.serviceId,
      link: order.link,
      quantity: order.quantity,
    };
    if (order.dripFeed) {
      params.runs = order.runs;
      params.interval = order.interval;
    }
    const resp = await apiRequest("/api/smmstore/order", params);
    if (resp?.error) {
      updateOrder(order.id, { status: "Failed" });
      return;
    }
    const orderId = String(resp?.order || "").trim();
    if (!orderId) {
      updateOrder(order.id, { status: "Failed" });
      return;
    }
    updateOrder(order.id, { orderId, status: "In Queue" });
  };

  const submitOrder = () => {
    setOrderError("");
    if (!hasKey) {
      setOrderError("Missing API key. Set it in Profile.");
      return;
    }
    if (!service) {
      setOrderError("Please select a service.");
      return;
    }
    if (!link.trim()) {
      setOrderError("Please enter a link.");
      return;
    }
    if (!quantity || Number(quantity) <= 0) {
      setOrderError("Quantity must be greater than 0.");
      return;
    }

    const runAt = buildRunAt();
    const now = new Date();
    const orderId = `ord_${Date.now()}`;
    const newOrder = {
      id: orderId,
      runAt: runAt.toISOString(),
      service,
      serviceId: serviceIdMap[service] || service.split(" - ")[0]?.trim(),
      link: link.trim(),
      quantity: String(quantity),
      status: "In Queue",
      orderId: "",
      charge: "",
      remains: "",
      dripFeed,
      runs: dripFeed ? String(runs || "") : "",
      interval: dripFeed ? String(interval || "") : "",
    };

    addOrderToQueue(newOrder);

    if (runAt <= now) {
      sendOrder(newOrder);
    }
  };

  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      orders.forEach((order) => {
        if (order.orderId || order.status !== "In Queue") return;
        if (new Date(order.runAt).getTime() <= now) {
          sendOrder(order);
        }
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [orders]);

  useEffect(() => {
    const poll = setInterval(() => {
      orders.forEach(async (order) => {
        if (!order.orderId) return;
        const statusLower = (order.status || "").toLowerCase();
        if (
          statusLower.includes("completed") ||
          statusLower.includes("partial") ||
          statusLower.includes("cancel")
        ) {
          return;
        }
        const resp = await apiRequest("/api/smmstore/status", {
          order: order.orderId,
        });
        if (resp?.error) return;
        updateOrder(order.id, {
          status: resp.status || "Unknown",
          charge: resp.charge || "",
          remains: resp.remains || resp.remain || "",
        });
      });
    }, 15000);
    return () => clearInterval(poll);
  }, [orders]);

  return (
    <Stack spacing={2}>
      <Paper
        elevation={0}
        sx={{
          p: 2,
          borderRadius: 2,
          border: `1px solid ${theme.palette.divider}`,
          bgcolor:
            theme.palette.mode === "dark"
              ? "rgba(17,17,17,0.6)"
              : "rgba(255,255,255,0.9)",
        }}
      >
        <Stack direction="row" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
          <Box>
            <Typography variant="h6" fontWeight="700">
              SMM Balance
            </Typography>
            {!hasKey && (
              <Typography variant="body2" color="text.secondary">
                Set your API key in Profile to load balance.
              </Typography>
            )}
            {hasKey && balanceError && (
              <Typography variant="body2" color="error">
                {balanceError}
              </Typography>
            )}
          </Box>

          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="h4" fontWeight="800" color={colors.greenAccent[400]}>
              {loadingBalance
                ? "..."
                : balance !== null
                  ? `${balance.toLocaleString()} ${balanceCurrency}`
                  : "--"}
            </Typography>
            <Button
              variant="outlined"
              size="small"
              onClick={() => fetchBalance()}
              disabled={!hasKey || loadingBalance}
            >
              Refresh
            </Button>
          </Stack>
        </Stack>
      </Paper>


      <Paper
        elevation={0}
        sx={{
          p: 2,
          borderRadius: 2,
          border: `1px solid ${theme.palette.divider}`,
          bgcolor:
            theme.palette.mode === "dark"
              ? "rgba(17,17,17,0.6)"
              : "rgba(255,255,255,0.9)",
        }}
      >
        <Stack spacing={2}>
          <Typography variant="h6" fontWeight="700">
            Order Information
          </Typography>

          <TextField
            label="Search Service"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            fullWidth
          />
          {search && filteredServices.length > 0 && (
            <Paper variant="outlined" sx={{ maxHeight: 240, overflow: "auto" }}>
              {filteredServices.map((item) => (
                <Box
                  key={item}
                  sx={{
                    px: 1.5,
                    py: 1,
                    cursor: "pointer",
                    "&:hover": { bgcolor: "action.hover" },
                  }}
                  onClick={() => handleSelectService(item)}
                >
                  <Typography variant="body2">{item}</Typography>
                </Box>
              ))}
            </Paper>
          )}

          <Stack direction="row" spacing={2} flexWrap="wrap">
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>Category</InputLabel>
              <Select
                value={category}
                label="Category"
                onChange={(e) => {
                  const next = e.target.value;
                  setCategory(next);
                  const items = servicesByCategory[next] || [];
                  if (items.length) {
                    const label = `${items[0].service} - ${items[0].name}`;
                    setService(label);
                    setSearch(label);
                  }
                }}
              >
                {Object.keys(servicesByCategory).map((cat) => (
                  <MenuItem key={cat} value={cat}>
                    {cat}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 320 }}>
              <InputLabel>Service</InputLabel>
              <Select
                value={service}
                label="Service"
                onChange={(e) => {
                  setService(e.target.value);
                  setSearch(e.target.value);
                }}
              >
                {(servicesByCategory[category] || []).map((item) => {
                  const label = `${item.service} - ${item.name}`;
                  return (
                    <MenuItem key={label} value={label}>
                      {label}
                    </MenuItem>
                  );
                })}
              </Select>
            </FormControl>
          </Stack>

          <Stack direction="row" spacing={2} flexWrap="wrap">
            <TextField
              label="Run Date"
              type="date"
              value={runDate}
              onChange={(e) => setRunDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
              size="small"
            />
            <TextField
              label="Time"
              type="time"
              value={runTime}
              onChange={(e) => setRunTime(e.target.value)}
              InputLabelProps={{ shrink: true }}
              size="small"
            />
          </Stack>

          <TextField
            label="Link"
            value={link}
            onChange={(e) => setLink(e.target.value)}
            fullWidth
            size="small"
          />
          <TextField
            label="Quantity"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            size="small"
            sx={{ maxWidth: 180 }}
          />

          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
            <Button
              variant={dripFeed ? "contained" : "outlined"}
              onClick={() => setDripFeed((prev) => !prev)}
            >
              Drip-Feed {dripFeed ? "On" : "Off"}
            </Button>
            {dripFeed && (
              <>
                <TextField
                  label="Runs"
                  value={runs}
                  onChange={(e) => setRuns(e.target.value)}
                  size="small"
                  sx={{ maxWidth: 120 }}
                />
                <TextField
                  label="Interval (min)"
                  value={interval}
                  onChange={(e) => setInterval(e.target.value)}
                  size="small"
                  sx={{ maxWidth: 150 }}
                />
              </>
            )}
          </Stack>

          {orderError && (
            <Typography variant="body2" color="error">
              {orderError}
            </Typography>
          )}

          <Button
            variant="contained"
            color="secondary"
            onClick={submitOrder}
            disabled={!hasKey || loadingServices}
            sx={{ maxWidth: 180 }}
          >
            Submit
          </Button>
        </Stack>
      </Paper>

      <Paper
        elevation={0}
        sx={{
          borderRadius: 2,
          border: `1px solid ${theme.palette.divider}`,
          overflow: "hidden",
        }}
      >
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Run Time</TableCell>
                <TableCell>Order ID</TableCell>
                <TableCell>Service</TableCell>
                <TableCell>Link</TableCell>
                <TableCell>Quantity</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {orders.map((order) => (
                <TableRow key={order.id}>
                  <TableCell>
                    {order.runAt
                      ? new Date(order.runAt).toLocaleString()
                      : ""}
                  </TableCell>
                  <TableCell>{order.orderId}</TableCell>
                  <TableCell>{order.serviceId}</TableCell>
                  <TableCell>
                    <a
                      href={order.link}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: colors.blueAccent[400] }}
                    >
                      {order.link}
                    </a>
                  </TableCell>
                  <TableCell>{order.quantity}</TableCell>
                  <TableCell>{order.status}</TableCell>
                </TableRow>
              ))}
              {orders.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Typography variant="body2" color="text.secondary">
                      No orders yet.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Stack direction="row" spacing={2} flexWrap="wrap">
      </Stack>
    </Stack>
  );
};

export default Smmstore;
